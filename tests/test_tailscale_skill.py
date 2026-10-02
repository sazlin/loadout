"""Contracts for the vendored tailscale skill on the base loadout."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from loadout.frontmatter import parse_skill_md
from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO / "skills" / "tailscale"
SKILL_MD = SKILL_ROOT / "SKILL.md"
PINNED_SHA256 = "4d9ed74813e586ae608cab4cec5ecc57f18c0e2d5a4ee18b3a56521b11d050ed"
PINNED_COMMIT = "4f05d353efc56962546aa26ccc59bb08ca699ad1"


def test_tailscale_skill_parses() -> None:
    assert SKILL_MD.is_file(), SKILL_MD
    meta = parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name="tailscale")
    assert meta.name == "tailscale"
    assert "Tailscale" in meta.description


def test_base_loadout_includes_tailscale() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert "skills/tailscale" in srcs


def test_tailscale_source_pin_matches_skill_bytes() -> None:
    source = (SKILL_ROOT / "SOURCE.md").read_text()
    digest = hashlib.sha256(SKILL_MD.read_bytes()).hexdigest()
    assert digest == PINNED_SHA256
    assert PINNED_SHA256 in source
    assert PINNED_COMMIT in source
    assert "tailscale/tailscale-skill" in source
    assert "curl | sh" in source


def test_tailscale_body_refuses_unpinned_install() -> None:
    text = SKILL_MD.read_text()
    assert "curl -fsSL https://tailscale.com/install.sh | sh" not in text
    assert "do not pipe a remote script into a shell" in text.lower()
    install = (SKILL_ROOT / "references" / "installation.md").read_text()
    assert "curl -fsSL https://tailscale.com/install.sh | sh" not in install
    containers = (SKILL_ROOT / "references" / "containers.md").read_text()
    assert "tailscale/tailscale:latest" not in containers
    assert "--version <chart-version>" in containers


def test_tailscale_evals_are_colocated() -> None:
    evals = SKILL_ROOT / "evals" / "evals.json"
    payload = json.loads(evals.read_text())
    assert payload["skill_name"] == "tailscale"
    prompts = [entry["prompt"] for entry in payload["evals"]]
    assert any("Install Tailscale" in prompt for prompt in prompts)
    assert any("AWS keys" in prompt for prompt in prompts)
