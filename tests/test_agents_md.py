"""Contracts for AGENTS.md Cursor Cloud workflow notes."""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AGENTS_MD = REPO / "AGENTS.md"


def test_agents_md_documents_just_recipes_take_no_file_arguments() -> None:
    text = AGENTS_MD.read_text().lower()
    assert "just" in text
    assert "no file arguments" in text
    assert "uv run pytest" in text


def test_agents_md_documents_fetch_before_push_on_shared_branches() -> None:
    text = AGENTS_MD.read_text().lower()
    assert "shared feature" in text
    assert "fetch" in text
    assert "rebase" in text


def test_agents_md_documents_skill_source_hash_pin_refresh() -> None:
    text = AGENTS_MD.read_text().lower()
    assert "vendored skill" in text
    assert "source.md" in text
    assert "pin" in text


def test_agents_md_documents_unique_walkthrough_artifact_names() -> None:
    text = AGENTS_MD.read_text().lower()
    assert "walkthrough artifact" in text
    assert "unique name" in text
