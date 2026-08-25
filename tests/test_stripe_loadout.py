"""Contracts for the stripe loadout and vendored Stripe agent skills."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
SKILL_NAMES = (
    "connect-recommend",
    "connect-required-verification-information",
    "stripe-apps",
    "stripe-best-practices",
    "stripe-directory",
    "stripe-docs",
    "stripe-projects",
    "upgrade-stripe",
)
SKILL_SRCS = tuple(f"skills/{name}" for name in SKILL_NAMES)


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def test_stripe_loadout_ships_vendored_stripe_skills() -> None:
    loadout = load_loadout(REPO / "loadouts" / "stripe.yaml")
    assert loadout.name == "stripe"
    assert loadout.extends == ["base"]
    assert {entry["src"] for entry in loadout.skills} == set(SKILL_SRCS)
    assert loadout.rules == []
    assert loadout.agents == []
    assert loadout.mcps == []


def test_stripe_sync_vendors_skills_and_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [stripe]
""",
    )

    sync(project)

    for name in SKILL_NAMES:
        skill = project / ".claude" / "skills" / name / "SKILL.md"
        assert skill.is_file(), skill
        assert f"name: {name}" in skill.read_text()
        assert not (project / ".claude" / "skills" / name / "evals").exists()

    assert (project / ".claude/agents/davinci.md").is_file()
    assert (project / ".cursor/rules/repo-conventions.mdc").is_file()


def test_base_sync_does_not_vendor_stripe_skills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [base]
""",
    )

    sync(project)

    for name in SKILL_NAMES:
        assert not (project / ".claude" / "skills" / name).exists()


def test_stripe_skill_evals_are_colocated() -> None:
    for name, src in zip(SKILL_NAMES, SKILL_SRCS, strict=True):
        evals = REPO / src / "evals" / "evals.json"
        payload = json.loads(evals.read_text())
        assert payload["skill_name"] == name
        assert payload["evals"]
        for index, entry in enumerate(payload["evals"]):
            for relative in entry.get("files", []):
                path = REPO / src / relative
                assert path.is_file(), f"{name} evals[{index}] missing {relative}"


FORBIDDEN_INSTALLS = (
    "npm i -g @stripe/cli",
    "npx skills add https://github.com/stripe/ai",
    "Bash(brew install stripe/stripe-cli/stripe)",
    "Bash(npx skills add https://docs.stripe.com *)",
)


def test_stripe_skills_do_not_instruct_unpinned_installs() -> None:
    for src in SKILL_SRCS:
        text = (REPO / src / "SKILL.md").read_text()
        for needle in FORBIDDEN_INSTALLS:
            assert needle not in text, f"{src} still instructs {needle!r}"


def test_stripe_projects_does_not_handoff_to_generated_skill() -> None:
    text = (REPO / "skills" / "stripe-projects" / "SKILL.md").read_text().lower()
    assert "do not invoke" in text
    assert "stripe-projects-cli" in text
    assert "skill tool with name `stripe-projects-cli`" not in text
    assert "--accept-tos --yes" not in text


def test_stripe_skill_source_pins_exist() -> None:
    for src in SKILL_SRCS:
        source = REPO / src / "SOURCE.md"
        text = source.read_text()
        assert "docs.stripe.com/.well-known/skills/index.json" in text
        assert "just add_skill" in text
        assert "evals/" in text
