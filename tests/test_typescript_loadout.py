"""Contracts for the typescript loadout authoring rule."""

from __future__ import annotations

from pathlib import Path

from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
RULE_SRC = "rules/typescript/typescript-code-style.mdc"


def test_typescript_loadout_extends_base_and_coding() -> None:
    loadout = load_loadout(REPO / "loadouts" / "typescript.yaml")
    assert loadout.extends == ["base", "coding"]
    assert RULE_SRC in {entry["src"] for entry in loadout.rules}


def test_typescript_rule_covers_html_text_and_cli_arity() -> None:
    text = (REPO / RULE_SRC).read_text().lower()
    assert "skip-depth" in text
    assert "match-until-close" in text
    assert "&copy;" in text or "copy" in text
    assert "mdash" in text and "hellip" in text
    assert "iframe" in text
    assert "process.argv[2]" in text
    assert "http:" in text and "https:" in text
    assert "abortsignal.timeout" in text
    assert "5_242_880" in text
    assert "unbounded" in text
    assert "scrape.ts" in (REPO / RULE_SRC).read_text()
    assert "main()" in (REPO / RULE_SRC).read_text()
    assert "<body>" in (REPO / RULE_SRC).read_text()
