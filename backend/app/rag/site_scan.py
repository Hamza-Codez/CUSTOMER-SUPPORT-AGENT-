"""Read a seller's own website and find the pages that state their policies.

Onboarding used to be a paste box: the seller had to find, copy and format the
policies they had already published. This does that part for them — paste the
storefront URL, and what comes back is a list of candidate pages with the text
we would ingest, for them to approve.

Three deliberate limits, because the alternative to each is a lie:

- **It finds policies, never orders.** Order status lives behind an account, and
  anything scraped that resembled one would be someone else's. Live order data
  needs an API key or an upload, and the UI says so.
- **Nothing is ingested without a click.** The seller sees the extracted text
  before it becomes something the agent will quote at a customer.
- **It reports what it could not read.** A page behind JavaScript comes back as a
  miss rather than as an empty policy, which would ground an answer in nothing.

On fetching URLs a user supplied: this runs server-side, so it is a
request-forgery surface. `_safe_url` refuses anything that is not public http(s)
— by scheme, by hostname, and by every IP the hostname resolves to.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

# How much of a site to look at. Small on purpose: a storefront's policies are
# linked from the footer of the front page, and a deep crawl would be slower,
# ruder to the seller's server, and no more accurate.
MAX_CANDIDATES = 8
MAX_BYTES = 1_500_000
FETCH_TIMEOUT = 12.0
MAX_PASSAGE_CHARS = 6000
MIN_PASSAGE_CHARS = 180

USER_AGENT = "DigitalFTE-SiteScan/1.0 (+policy discovery for the site owner)"

# What a policy page is called, in descending confidence.
#
# `url_only` marks a term too generic to trust in anchor text. Measured against a
# real storefront: "support" matched the words "sports bra support guide" and
# proposed a product page as a policy. Specific words like "refund" do not have
# that problem, so they are still matched either way.
POLICY_TERMS: list[tuple[str, str, bool]] = [
    ("refund", "Refunds", False),
    ("return", "Returns", False),
    ("shipping", "Shipping", False),
    ("delivery", "Delivery", False),
    ("dispatch", "Dispatch", False),
    ("warranty", "Warranty", False),
    ("guarantee", "Guarantee", False),
    ("exchange", "Exchanges", False),
    ("cancellation", "Cancellations", False),
    ("faq", "FAQ", True),
    ("help", "Help", True),
    ("support", "Support", True),
    ("terms", "Terms", True),
    ("privacy", "Privacy", True),
    ("policies", "Policies", True),
    ("policy", "Policy", True),
]

# Pages that match a term but never carry prose a support agent should quote.
# Cookie and consent notices are the common case: they match "policy", they are
# long, and no customer has ever asked one a support question.
EXCLUDE = re.compile(
    r"(/cart|/checkout|/account|/login|/register|/search|/collections?/|"
    r"/products?/|cookie|consent|accessibility|modern-slavery|"
    r"\.(jpg|jpeg|png|gif|svg|pdf|zip|css|js)$)",
    re.IGNORECASE,
)

# Chrome that survives tag-stripping and would otherwise become "policy" text.
NOISE = re.compile(
    r"^(add to cart|subscribe|sign up|log ?in|menu|search|skip to content|"
    r"cookie|accept|close|©|share|tweet|\d+)$",
    re.IGNORECASE,
)


@dataclass
class ScannedPage:
    url: str
    title: str
    topic: str
    text: str
    # Why this page was picked, so the seller can see we did not guess.
    matched: str = ""


@dataclass
class ScanReport:
    site: str
    pages: list[ScannedPage] = field(default_factory=list)
    # URLs we tried and could not use, with the reason. Reported rather than
    # silently dropped: "we found 2 pages" reads very differently when you know
    # four others failed.
    skipped: list[tuple[str, str]] = field(default_factory=list)
    note: str = ""


class _Extractor(HTMLParser):
    """Tags out, structure kept.

    Written against `html.parser` rather than pulling in a parsing library: this
    needs to survive arbitrary storefront HTML, and a dependency whose failure
    modes we do not know is a worse bet than 60 lines we can read. Headings are
    kept because they are what a passage gets titled with.
    """

    SKIP = {"script", "style", "noscript", "template", "svg", "nav", "footer"}
    BLOCK = {
        "p", "div", "li", "tr", "br", "section", "article",
        "h1", "h2", "h3", "h4", "h5", "h6",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._skip_depth = 0
        self._in_title = False
        self._heading: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in {"h1", "h2", "h3"}:
            self._heading = tag
            self.parts.append("\n\n## ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in self.BLOCK:
            self.parts.append("\n")
            if tag == self._heading:
                self._heading = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
            return
        text = data.strip()
        if text:
            self.parts.append(text + " ")

    def result(self) -> str:
        joined = "".join(self.parts)
        lines = []
        for raw in joined.splitlines():
            line = re.sub(r"[ \t]+", " ", raw).strip()
            if line and not NOISE.match(line):
                lines.append(line)
        # Collapse runs of blank lines the block handling leaves behind.
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


class _LinkFinder(HTMLParser):
    """Every href with the text of its anchor, which is half the signal."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


def _safe_url(raw: str) -> str | None:
    """A public http(s) URL, or None.

    The seller supplies this and our server fetches it, so this is the request
    forgery boundary. Every resolved address is checked, not just the hostname:
    a name that resolves to 169.254.169.254 is the whole attack.
    """
    value = raw.strip()
    if not value:
        return None
    if "://" not in value:
        value = f"https://{value}"

    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None

    host = parsed.hostname
    if host.lower() in {"localhost", "localhost.localdomain"} or host.endswith(
        (".local", ".internal")
    ):
        return None

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return None

    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return None
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return None

    return parsed.geturl()


def _score(url: str, anchor: str) -> tuple[int, str, str]:
    """(score, topic, what matched). Zero means not a policy page."""
    path = urlsplit(url).path.lower()
    text = anchor.lower()
    best = (0, "", "")
    for index, (term, topic, url_only) in enumerate(POLICY_TERMS):
        weight = len(POLICY_TERMS) - index
        if term in path:
            # The URL is the stronger signal: anchor text is often "click here".
            score = weight * 2
            if score > best[0]:
                best = (score, topic, f"URL contains “{term}”")
        elif not url_only and term in text and weight > best[0]:
            best = (weight, topic, f"link text contains “{term}”")
    return best


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        response = await client.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    if "html" not in response.headers.get("content-type", "").lower():
        return None
    return response.text[:MAX_BYTES]


async def scan_site(raw_url: str) -> ScanReport:
    """Find and extract the policy pages linked from a storefront's front page."""
    root = _safe_url(raw_url)
    if root is None:
        return ScanReport(
            site=raw_url.strip(),
            note=(
                "That doesn't look like a public website address. Use the full "
                "URL of your live storefront, e.g. https://yourstore.com."
            ),
        )

    report = ScanReport(site=root)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}

    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT,
        follow_redirects=True,
        max_redirects=4,
        headers=headers,
    ) as client:
        home = await _fetch(client, root)
        if home is None:
            report.note = (
                "Couldn't read that page. Check the address is right and that the "
                "site is reachable from the public internet."
            )
            return report

        finder = _LinkFinder()
        finder.feed(home)

        origin = f"{urlsplit(root).scheme}://{urlsplit(root).netloc}"
        seen: set[str] = set()
        candidates: list[tuple[int, str, str, str]] = []

        for href, anchor in finder.links:
            absolute = urljoin(root, href)
            # Same site only. Following a link to a payment processor's returns
            # policy and calling it the seller's would be exactly wrong.
            if not absolute.startswith(origin):
                continue
            # Fragment and query dropped: the same policy page reached with a
            # campaign parameter is the same page, and keeping it would spend one
            # of the eight slots twice.
            absolute = absolute.split("#")[0].split("?")[0].rstrip("/")
            if not absolute or absolute in seen or EXCLUDE.search(absolute):
                continue
            score, topic, matched = _score(absolute, anchor)
            if score == 0:
                continue
            seen.add(absolute)
            candidates.append((score, absolute, topic, matched))

        candidates.sort(key=lambda c: -c[0])
        candidates = candidates[:MAX_CANDIDATES]

        if not candidates:
            report.note = (
                "No policy pages were linked from that page. If your policies "
                "live elsewhere, paste them in directly on the next step."
            )
            return report

        pages = await asyncio.gather(
            *(_fetch(client, url) for _, url, _, _ in candidates)
        )

    for (_, url, topic, matched), html in zip(candidates, pages):
        if html is None:
            report.skipped.append((url, "couldn't be fetched"))
            continue
        extractor = _Extractor()
        extractor.feed(html)
        text = extractor.result()
        if len(text) < MIN_PASSAGE_CHARS:
            # Almost always a page rendered by JavaScript. Saying so is the point:
            # ingesting the empty shell would ground an answer in nothing.
            report.skipped.append((url, "no readable text — the page may need JavaScript"))
            continue
        report.pages.append(
            ScannedPage(
                url=url,
                title=(extractor.title.strip() or topic)[:160],
                topic=topic,
                text=text[:MAX_PASSAGE_CHARS],
                matched=matched,
            )
        )

    if not report.pages:
        report.note = (
            "Found pages that looked right but couldn't read text from any of "
            "them. Paste your policies in directly instead."
        )
    return report
