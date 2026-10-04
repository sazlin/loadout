"""Contracts for the superpowers orca-native-worktree rule."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from loadout.frontmatter import parse_rule
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
RULE_SRC = "rules/core/orca-native-worktree.mdc"
RULE_DEST = ".cursor/rules/orca-native-worktree.mdc"

_REQUIRED = (
    ".claude/skills/orca-cli/skill.md",
    "orca_cli_command",
    "orca_dev_repo_root",
    "orca-managed",
    "using-git-worktrees",
    "skip step 1b",
    "do not run [`git worktree add`]",
    "do not run `orca open`",
    "do not invent flags",
)

# An unnegated instruction to create the checkout with git.
_UNNEGATED_ADD = re.compile(r"(?<!do not )run `git worktree add`", re.IGNORECASE)


def _holds_orca_worktree_line(text: str) -> bool:
    """True when an Orca session must use the Orca CLI and git add stays the fallback."""
    lowered = text.lower()
    if any(phrase not in lowered for phrase in _REQUIRED):
        return False
    if "either condition is false" not in lowered:
        return False
    return _UNNEGATED_ADD.search(text) is None


def test_superpowers_loadout_includes_orca_native_worktree_rule() -> None:
    loadout = load_loadout(REPO / "loadouts" / "superpowers.yaml")
    assert RULE_SRC in {entry["src"] for entry in loadout.rules}


def test_base_and_orca_loadouts_omit_orca_native_worktree_rule() -> None:
    for name in ("base", "orca"):
        loadout = load_loadout(REPO / "loadouts" / f"{name}.yaml")
        assert RULE_SRC not in {entry["src"] for entry in loadout.rules}


def test_orca_native_worktree_rule_is_always_on() -> None:
    path = REPO / RULE_SRC
    text = path.read_text()
    meta = parse_rule(path, text)
    assert meta.always_apply is True
    assert _holds_orca_worktree_line(text)


def test_git_worktree_add_advice_fails_the_orca_worktree_contract() -> None:
    """Naming the Orca CLI is not enough when the text still runs git worktree add."""
    bad = (
        "When .claude/skills/orca-cli/SKILL.md exists and ORCA_CLI_COMMAND "
        "or ORCA_DEV_REPO_ROOT is set, or the terminal is Orca-managed, "
        "run `git worktree add`. Skip Step 1b is optional. "
        "using-git-worktrees. Do not run `ORCA open`. Do not invent flags. "
        "Either condition is false."
    )
    assert not _holds_orca_worktree_line(bad)
    assert _holds_orca_worktree_line((REPO / RULE_SRC).read_text())


def _sync_loadout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> Path:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text(
        f"source: https://github.com/sazlin/loadout\nref: main\nloadouts: [{name}]\n"
    )
    sync(project)
    return project


def test_superpowers_sync_vendors_orca_native_worktree_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _sync_loadout(tmp_path, monkeypatch, "superpowers")
    vendored = (project / RULE_DEST).read_text()
    assert "alwaysApply: true" in vendored
    assert _holds_orca_worktree_line(vendored)
    agents = (project / "AGENTS.md").read_text()
    assert ".cursor/rules/orca-native-worktree.mdc" in agents
    assert "| Always |" in agents


def test_base_sync_does_not_vendor_orca_native_worktree_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _sync_loadout(tmp_path, monkeypatch, "base")
    assert not (project / RULE_DEST).exists()
