"""Parse the seller's documents into citable passages.

One section becomes one passage. Sections are the unit a human would quote, which
makes a citation land somewhere a person can actually check — the point of a
`source_ref` is that someone can open the document and see the sentence.

Anchors are **authored, not derived**: `## Damaged or faulty goods {#damaged-goods}`
pins the ref to `damaged-goods`. Slugging the heading instead would mean that
rewording a title silently breaks every citation already sitting in an audit log.
A missing anchor falls back to a slug, so a new document still parses, but the
seeded policies name theirs deliberately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "db" / "knowledge"

# "## Heading text {#explicit-anchor}" — the anchor is optional.
_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)(?:\s*\{#([a-z0-9-]+)\})?\s*$")


@dataclass(frozen=True)
class ParsedPassage:
    """A section of a source document, ready to embed and cite."""

    doc: str
    topic: str
    text: str
    source_ref: str
    heading_level: int


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse_markdown(content: str, doc_name: str) -> list[ParsedPassage]:
    """Split one document into passages, one per `##`/`###` section.

    Text before the first section heading is preamble — a title and a sentence of
    context — and is dropped. It describes the document rather than stating any
    policy, so citing it would point a customer at nothing useful.
    """
    passages: list[ParsedPassage] = []
    level: int | None = None
    topic: str | None = None
    anchor: str | None = None
    body: list[str] = []

    def flush() -> None:
        if topic is None:
            return
        text = "\n".join(body).strip()
        if not text:
            return
        passages.append(
            ParsedPassage(
                doc=doc_name,
                topic=topic,
                text=text,
                source_ref=f"{doc_name}#{anchor or slugify(topic)}",
                heading_level=level or 2,
            )
        )

    for line in content.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            topic = match.group(2).strip()
            anchor = match.group(3)
            body = []
        elif topic is not None:
            body.append(line)

    flush()
    return passages


def parse_directory(directory: Path | None = None) -> list[ParsedPassage]:
    """Parse every markdown document in the knowledge directory, name-ordered.

    A missing directory yields nothing rather than raising. This runs at import
    time to build the in-memory store's seed rows, so on a deployment that ships
    only the code — no demo documents — an exception here would take down the
    whole application at startup over content production does not use. A real
    tenant's policies live in the database.
    """
    root = directory or KNOWLEDGE_DIR
    if not root.is_dir():
        return []

    passages: list[ParsedPassage] = []
    for path in sorted(root.glob("*.md")):
        passages.extend(
            parse_markdown(path.read_text(encoding="utf-8"), path.name)
        )
    return passages
