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

# Unnegated `run `git worktree add`` or `run [`git worktree add`]` (optional link).
_UNNEGATED_ADD = re.compile(r"(?<!do not )run \[?`git worktree add`", re.IGNORECASE)
_FALSE_BRANCH_FORCES_1B = re.compile(
    r"either condition is false.{0,240}(?:skip step 1a|run step 1b|including step 1b)",
    re.IGNORECASE | re.DOTALL,
)


def _holds_orca_worktree_line(text: str) -> bool:
    """True when an Orca session must use the Orca CLI and git worktree add stays the fallback."""
    lowered = text.lower()
    if any(phrase not in lowered for phrase in _REQUIRED):
        return False
    if "either condition is false" not in lowered:
        return False
    if _FALSE_BRANCH_FORCES_1B.search(text):
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
    false_branch = text.lower().split("either condition is false", 1)[1]
    assert "step 1a" in false_branch
    assert "as written" in false_branch
    assert "including step 1b" not in false_branch
    assert "run step 1b" not in false_branch


_CONTRACT_PHRASES = (
    "When .claude/skills/orca-cli/SKILL.md exists and ORCA_CLI_COMMAND "
    "or ORCA_DEV_REPO_ROOT is set, or the terminal is Orca-managed, "
    "Skip Step 1b is optional. using-git-worktrees. "
    "Do not run [`git worktree add`]. Do not run `ORCA open`. Do not invent flags. "
    "Either condition is false. "
)


def test_unnegated_add_matches_linked_and_unlinked_spellings() -> None:
    linked = "run [`git worktree add`](https://git-scm.com/docs/git-worktree)"
    assert _UNNEGATED_ADD.search(linked)
    assert _UNNEGATED_ADD.search("run `git worktree add`")
    assert _UNNEGATED_ADD.search("Do not run [`git worktree add`](https://git-scm.com/docs/git-worktree)") is None


def test_git_worktree_add_advice_fails_the_orca_worktree_contract() -> None:
    """Naming the Orca CLI is not enough when the text still runs git worktree add."""
    bad = (
        "When .claude/skills/orca-cli/SKILL.md exists and ORCA_CLI_COMMAND "
        "or ORCA_DEV_REPO_ROOT is set, or the terminal is Orca-managed, "
        "run `git worktree add`. Skip Step 1b is optional. "
        "using-git-worktrees. Do not run `ORCA open`. Do not invent flags. "
        "Either condition is false."
    )
    linked_bad = _CONTRACT_PHRASES + "Also run [`git worktree add`](https://git-scm.com/docs/git-worktree)."
    assert not _holds_orca_worktree_line(bad)
    assert not _holds_orca_worktree_line(linked_bad)


def test_false_branch_that_forces_step_1b_fails_the_orca_worktree_contract() -> None:
    """A false branch that skips Step 1a or runs Step 1b fails the contract."""
    false_branch_bad = _CONTRACT_PHRASES + "If either condition is false, skip Step 1a and run Step 1b."
    assert not _holds_orca_worktree_line(false_branch_bad)


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
