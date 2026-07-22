"""Loading the knowledge base from real documents.

The proposal asks for answers grounded in *our docs*. That only means something
if the docs are files someone can edit, and if long documents are split into
passages that retrieve individually.
"""
from __future__ import annotations

import knowledge
from store import mock_store


# --- parsing -----------------------------------------------------------------

def test_the_h1_names_the_document():
    passages = knowledge.parse_document("# Refund policy\n\nRefunds take 5 days.", "fallback")
    assert passages == [{"title": "Refund policy", "body": "Refunds take 5 days."}]


def test_the_filename_is_used_when_there_is_no_h1():
    passages = knowledge.parse_document("Refunds take 5 days.", "Refund Policy")
    assert passages[0]["title"] == "Refund Policy"


def test_each_section_becomes_its_own_passage():
    """A long document embedded whole retrieves badly — the relevant paragraph
    gets averaged away. Sections are the unit of retrieval."""
    passages = knowledge.parse_document(
        "# Shipping\n\n## Domestic\nTwo days.\n\n## International\nTen days.",
        "shipping")

    assert [p["title"] for p in passages] == ["Shipping — Domestic", "Shipping — International"]
    assert passages[0]["body"] == "Two days."
    assert passages[1]["body"] == "Ten days."


def test_a_section_title_survives_into_the_passage_title():
    """So a retrieved answer can still say where it came from."""
    passages = knowledge.parse_document("# Warranty\n\n## Coverage\nFive years.", "w")
    assert passages[0]["title"] == "Warranty — Coverage"


def test_a_document_without_sections_stays_whole():
    passages = knowledge.parse_document("# Warranty\n\nFive years on everything.", "w")
    assert len(passages) == 1


def test_an_over_long_section_is_split_on_paragraph_boundaries():
    paragraph = "This is a sentence about the policy. " * 12   # ~440 chars
    text = "# Policy\n\n" + "\n\n".join([paragraph] * 5)         # ~2200 chars

    passages = knowledge.parse_document(text, "policy")

    assert len(passages) > 1
    assert all(len(p["body"]) <= knowledge.MAX_PASSAGE_CHARS for p in passages)
    assert all("1 of" in p["title"] or "of" in p["title"] for p in passages)
    # Nothing may be lost in the split.
    assert sum(p["body"].count("sentence about the policy") for p in passages) == 60


def test_markdown_noise_is_stripped():
    passages = knowledge.parse_document("# FAQ\n\n- **Bold** item with `code`", "faq")
    assert passages[0]["body"] == "Bold item with code"


def test_empty_sections_are_dropped():
    passages = knowledge.parse_document("# Doc\n\n## Empty\n\n## Real\nContent.", "d")
    assert [p["title"] for p in passages] == ["Doc — Real"]


# --- loading from disk -------------------------------------------------------

def test_documents_load_from_the_knowledge_folder(tmp_path):
    (tmp_path / "faq.md").write_text("# FAQ\n\n## Returns\nThirty days.", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("Plain text works too.", encoding="utf-8")

    titles = [p["title"] for p in knowledge.load_documents(tmp_path)]
    assert "FAQ — Returns" in titles
    assert "Notes" in titles


def test_folder_documentation_is_not_treated_as_knowledge(tmp_path):
    """Otherwise the agent answers a customer with Markdown instructions."""
    (tmp_path / "README.md").write_text("# How to use this folder\n\nDrop files here.",
                                        encoding="utf-8")
    (tmp_path / "_template.md").write_text("# Template\n\nBoilerplate.", encoding="utf-8")
    (tmp_path / "real.md").write_text("# Real\n\nActual content.", encoding="utf-8")

    assert [p["title"] for p in knowledge.load_documents(tmp_path)] == ["Real"]


def test_a_missing_folder_is_not_an_error(tmp_path):
    assert knowledge.load_documents(tmp_path / "nope") == []


def test_non_documents_are_ignored(tmp_path):
    (tmp_path / "photo.png").write_bytes(b"\x89PNG")
    (tmp_path / "data.json").write_text("{}", encoding="utf-8")
    assert knowledge.load_documents(tmp_path) == []


# --- what the agent actually serves ------------------------------------------

def test_the_live_knowledge_base_comes_from_the_document_folder():
    """If this ever falls back, someone deleted or broke db/knowledge/."""
    assert mock_store.KNOWLEDGE_BASE is not mock_store._FALLBACK_KNOWLEDGE
    titles = {d["title"] for d in mock_store.KNOWLEDGE_BASE}
    assert {"Refund policy", "Shipping times", "Warranty"} <= titles


def test_the_knowledge_base_can_be_reloaded_without_a_restart():
    assert mock_store.reload_knowledge() == len(mock_store.KNOWLEDGE_BASE)


def test_every_passage_has_the_shape_the_store_contract_promises():
    for doc in mock_store.KNOWLEDGE_BASE:
        assert set(doc) == {"title", "body"}
        assert doc["title"].strip() and doc["body"].strip()
