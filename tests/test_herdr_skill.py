"""Contracts for the vendored herdr skill on the base and coding loadouts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from loadout.frontmatter import parse_skill_md
from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO / "skills" / "herdr"
SKILL_MD = SKILL_ROOT / "SKILL.md"
PINNED_SHA256 = "03855a7a1f9d0aa1ba6444fed2e4971adf796e91e73001d8f2472f5f9e5f659f"
PINNED_COMMIT = "065ef9d6a531c49fb8bee7e818ef837065b21ee9"


def test_herdr_skill_parses() -> None:
    assert SKILL_MD.is_file(), SKILL_MD
    meta = parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name="herdr")
    assert meta.name == "herdr"
    assert "HERDR_ENV=1" in meta.description


def test_base_and_coding_loadouts_include_herdr() -> None:
    for name in ("base", "coding"):
        loadout = load_loadout(REPO / "loadouts" / f"{name}.yaml")
        srcs = {entry["src"] for entry in loadout.skills}
        assert "skills/herdr" in srcs


def test_herdr_source_pin_matches_skill_bytes() -> None:
    source = (SKILL_ROOT / "SOURCE.md").read_text()
    digest = hashlib.sha256(SKILL_MD.read_bytes()).hexdigest()
    assert digest == PINNED_SHA256
    assert PINNED_SHA256 in source
    assert PINNED_COMMIT in source
    assert "v0.9.1" in source
    assert "herdrdev/herdr" in source


def test_herdr_body_requires_explicit_use_and_blocks_server_stop() -> None:
    text = SKILL_MD.read_text()
    lowered = text.lower()
    assert "do not use merely because" in lowered
    assert 'test "${herdr_env:-}" = 1' in lowered
    assert "herdr server stop" in lowered
    assert "--no-focus" in text


def test_herdr_evals_are_colocated() -> None:
    evals = SKILL_ROOT / "evals" / "evals.json"
    payload = json.loads(evals.read_text())
    assert payload["skill_name"] == "herdr"
    prompts = [entry["prompt"] for entry in payload["evals"]]
    assert any("HERDR_ENV is unset" in prompt for prompt in prompts)
    assert any("Do not mention Herdr" in prompt for prompt in prompts)
