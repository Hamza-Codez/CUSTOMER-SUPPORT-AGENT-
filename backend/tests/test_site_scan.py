"""Reading a seller's own site to find their policy pages.

The extraction tests run on fixed HTML, so they assert our parsing rather than
the shape of any real storefront. The `_safe_url` tests are the ones that matter
most: this feature makes the server fetch a URL a user typed, which is a request
forgery surface, and the guard is the only thing standing in front of it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag.site_scan import _Extractor, _LinkFinder, _safe_url, _score

OPS = {"Authorization": "Bearer ops-token"}


@pytest.fixture
def client(store):
    with TestClient(app) as c:
        yield c


class TestUrlGuard:
    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost/admin",
            "http://127.0.0.1:8000/",
            "https://127.0.0.1/",
            "http://169.254.169.254/latest/meta-data/",  # cloud metadata
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://[::1]/",
            "file:///etc/passwd",
            "ftp://example.com/",
            "http://router.local/",
            "",
            "   ",
        ],
    )
    def test_private_and_non_http_targets_are_refused(self, url):
        assert _safe_url(url) is None

    def test_a_public_https_url_is_accepted(self):
        assert _safe_url("https://example.com") == "https://example.com"

    def test_a_bare_domain_becomes_https(self):
        assert _safe_url("example.com") == "https://example.com"

    def test_an_unresolvable_host_is_refused(self):
        assert _safe_url("https://not-a-real-domain-zzz.invalid") is None


class TestScoring:
    @pytest.mark.parametrize(
        "url,expected_topic",
        [
            ("https://s.example/pages/refund-policy", "Refunds"),
            ("https://s.example/shipping", "Shipping"),
            ("https://s.example/pages/warranty", "Warranty"),
            ("https://s.example/faq", "FAQ"),
        ],
    )
    def test_policy_urls_score(self, url, expected_topic):
        score, topic, _ = _score(url, "")
        assert score > 0
        assert topic == expected_topic

    def test_an_ordinary_page_does_not(self):
        assert _score("https://s.example/about-us", "About us")[0] == 0

    def test_the_url_outweighs_the_anchor_text(self):
        """Anchor text is often "click here"; the path is the real signal."""
        by_url = _score("https://s.example/refunds", "click here")[0]
        by_text = _score("https://s.example/p/9", "refunds")[0]
        assert by_url > by_text

    def test_a_generic_word_in_link_text_is_not_enough(self):
        """Measured against a real storefront, not imagined.

        "support" in the anchor "sports bra support guide" proposed a product
        page as a policy. Generic terms now have to appear in the URL.
        """
        assert _score("https://s.example/pages/sports-bras", "support guide")[0] == 0
        assert _score("https://s.example/pages/help-centre", "read this")[0] > 0

    def test_a_specific_word_in_link_text_still_counts(self):
        assert _score("https://s.example/pages/x9", "our refund policy")[0] > 0


SAMPLE = """
<html><head><title>Returns Policy — Aeron</title></head>
<body>
  <nav><a href="/cart">Cart</a></nav>
  <script>var tracking = 1;</script>
  <style>.x { color: red }</style>
  <h1>Returns</h1>
  <p>You may return any item within 30 days of delivery.</p>
  <p>Items must be unused and in their original packaging.</p>
  <ul><li>Refunds are issued to the original payment method.</li></ul>
  <footer>© 2026</footer>
</body></html>
"""


class TestExtraction:
    def test_script_style_and_chrome_are_dropped(self):
        parser = _Extractor()
        parser.feed(SAMPLE)
        text = parser.result()
        assert "tracking" not in text
        assert "color: red" not in text
        assert "Cart" not in text
        assert "©" not in text

    def test_the_prose_survives(self):
        parser = _Extractor()
        parser.feed(SAMPLE)
        text = parser.result()
        assert "within 30 days of delivery" in text
        assert "original payment method" in text

    def test_the_title_is_captured(self):
        parser = _Extractor()
        parser.feed(SAMPLE)
        assert "Returns Policy" in parser.title

    def test_headings_are_kept_as_structure(self):
        parser = _Extractor()
        parser.feed(SAMPLE)
        assert "## Returns" in parser.result()

    def test_links_are_found_with_their_anchor_text(self):
        finder = _LinkFinder()
        finder.feed('<a href="/refunds">Our refund policy</a>')
        assert finder.links == [("/refunds", "Our refund policy")]


class TestEndpoint:
    def test_a_bad_url_is_reported_not_raised(self, client):
        r = client.post("/onboarding/scan", json={"url": "http://localhost"}, headers=OPS)
        assert r.status_code == 200
        body = r.json()
        assert body["pages"] == []
        assert "public website address" in body["note"]

    def test_a_customer_token_cannot_scan(self, client):
        r = client.post(
            "/onboarding/scan",
            json={"url": "https://example.com"},
            headers={"Authorization": "Bearer demo-token"},
        )
        assert r.status_code == 403

    def test_scanning_stores_nothing(self, client):
        """The seller approves before anything becomes quotable."""
        before = client.get("/dashboard/overview", headers=OPS).json()["policies"]
        client.post("/onboarding/scan", json={"url": "http://127.0.0.1"}, headers=OPS)
        after = client.get("/dashboard/overview", headers=OPS).json()["policies"]
        assert before == after
