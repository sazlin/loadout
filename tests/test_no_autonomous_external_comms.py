"""Contracts for the no-autonomous-external-comms core rule on the base loadout."""

from __future__ import annotations

from pathlib import Path

import pytest

from loadout.frontmatter import parse_rule
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
RULE_SRC = "rules/core/no-autonomous-external-comms.mdc"


def test_base_loadout_includes_no_autonomous_external_comms() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    assert RULE_SRC in {entry["src"] for entry in loadout.rules}


def test_no_autonomous_external_comms_always_applies() -> None:
    path = REPO / RULE_SRC
    text = path.read_text()
    meta = parse_rule(path, text)
    assert meta.always_apply is True
    lowered = meta.description.lower()
    assert "go/no-go" in lowered or "go / no-go" in lowered
    assert "the user" in lowered
    assert "their" in lowered
    assert "sean azlin" not in lowered
    assert "sazlin" not in lowered


def test_no_autonomous_external_comms_requires_explicit_go() -> None:
    text = (REPO / RULE_SRC).read_text().lower()
    assert "the user" in text
    assert "their" in text
    assert "sean azlin" not in text
    assert "sazlin/*" not in text and "sazlin/" not in text
    assert "go/no-go" in text or "go / no-go" in text
    assert "third-party" in text or "third party" in text or "3rd party" in text
    assert "assume" in text
    assert "permission" in text
    assert "do not post" in text or "don't post" in text or "must not post" in text


def test_base_sync_vendors_no_autonomous_external_comms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [base]\n")
    sync(project)
    dest = project / ".cursor/rules/no-autonomous-external-comms.mdc"
    assert dest.is_file()
    vendored = dest.read_text()
    assert "alwaysApply: true" in vendored
    assert "the user" in vendored.lower()
    assert "sean azlin" not in vendored.lower()
