"""The knowledge base, loaded from real documents on disk.

The proposal asks for answers "grounded in our docs". That means the KB has to
come from files you can edit, not from a Python literal — drop your FAQ, policy
and product documents into `db/knowledge/` as Markdown and they become what the
agent answers from.

Documents are split into **passages**, not embedded whole. A 2,000-word policy
document as a single vector retrieves badly: the one relevant paragraph gets
averaged away by everything around it. Splitting on `##` headings keeps each
passage about one thing, which is what makes retrieval land on the right answer.
"""
from __future__ import annotations

import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BACKEND_DIR / "db" / "knowledge"

SUFFIXES = (".md", ".markdown", ".txt")

# Notes about the folder are not knowledge about the business. Without this the
# agent would cheerfully answer a customer with instructions about Markdown.
IGNORED_STEMS = {"readme", "index", "_template"}

# Long enough to hold a real answer, short enough that one passage is one topic.
MAX_PASSAGE_CHARS = 1200


def _clean(text: str) -> str:
    """Collapse Markdown noise that adds nothing to a retrieved answer."""
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)   # bullets
    text = re.sub(r"\*\*|__|`", "", text)                           # emphasis
    text = re.sub(r"\n{2,}", "\n", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _split_long(title: str, body: str) -> list[dict]:
    """Break an over-long passage on paragraph boundaries, never mid-sentence."""
    if len(body) <= MAX_PASSAGE_CHARS:
        return [{"title": title, "body": body}]

    passages, buffer = [], ""
    for paragraph in body.split("\n"):
        if buffer and len(buffer) + len(paragraph) + 1 > MAX_PASSAGE_CHARS:
            passages.append(buffer.strip())
            buffer = paragraph
        else:
            buffer = f"{buffer}\n{paragraph}" if buffer else paragraph
    if buffer.strip():
        passages.append(buffer.strip())

    if len(passages) == 1:
        return [{"title": title, "body": passages[0]}]
    return [{"title": f"{title} ({i} of {len(passages)})", "body": p}
            for i, p in enumerate(passages, 1)]


def parse_document(text: str, fallback_title: str) -> list[dict]:
    """One document -> one or more `{title, body}` passages.

    `# Heading` names the document. Each `## Heading` becomes its own passage,
    titled "Document — Section" so a retrieved answer still says where it came
    from. A document with no `##` sections stays whole.
    """
    lines = text.strip().splitlines()
    doc_title = fallback_title
    start = 0
    if lines and lines[0].startswith("# "):
        doc_title = lines[0][2:].strip()
        start = 1

    sections: list[tuple[str, list[str]]] = []
    current_title, current_body = None, []
    for line in lines[start:]:
        if line.startswith("## "):
            if current_body or current_title:
                sections.append((current_title, current_body))
            current_title, current_body = line[3:].strip(), []
        else:
            current_body.append(line)
    if current_body or current_title:
        sections.append((current_title, current_body))

    passages = []
    for section_title, body_lines in sections:
        body = _clean("\n".join(body_lines))
        if not body:
            continue
        title = f"{doc_title} — {section_title}" if section_title else doc_title
        passages.extend(_split_long(title, body))
    return passages


def load_documents(directory: Path | None = None) -> list[dict]:
    """Every passage from every document in `db/knowledge/`, sorted for stability.

    Returns [] when the folder is missing or empty — the caller decides what to
    fall back to.
    """
    target = directory or KNOWLEDGE_DIR
    if not target.is_dir():
        return []

    passages = []
    for path in sorted(target.rglob("*")):
        if path.suffix.lower() not in SUFFIXES or not path.is_file():
            continue
        if path.stem.lower() in IGNORED_STEMS or path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        fallback = path.stem.replace("-", " ").replace("_", " ").strip().title()
        passages.extend(parse_document(text, fallback))
    return passages


def describe_source() -> str:
    """For the ingest script and /health-style diagnostics."""
    count = len(load_documents())
    if count:
        return f"{count} passages from {KNOWLEDGE_DIR.relative_to(BACKEND_DIR)}"
    return "built-in demo documents (db/knowledge/ is empty)"
