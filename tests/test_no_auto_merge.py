"""Contracts for the base no-auto-merge rule."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from loadout.frontmatter import parse_rule
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
RULE_SRC = "rules/core/no-auto-merge.mdc"
RULE_DEST = ".cursor/rules/no-auto-merge.mdc"

# Counter-example: tokens are present, but the body instructs enabling auto-merge.
ENABLE_AUTO_COUNTEREXAMPLE = (
    "Always pass `--auto` to enable auto-merge. Wait until every attached check "
    "has finished. Skip a check only with a high-confidence reason."
)

_NEVER_ENABLE = re.compile(r"never enable auto-merge", re.IGNORECASE)
_DO_NOT_PASS_AUTO = re.compile(r"do not pass `--auto`", re.IGNORECASE)
_AUTO_MERGE_API = re.compile(
    r"enablePullRequestAutoMerge|auto-merge API",
    re.IGNORECASE,
)
_ALWAYS_PASS_AUTO = re.compile(r"always pass `--auto`", re.IGNORECASE)
_SKIP_FAILED_BAN = re.compile(
    r"(?:failed|pending|cancelled|timed-out).{0,80}cannot be skipped",
    re.IGNORECASE | re.DOTALL,
)
_PLATFORM_SKIP = re.compile(r"skipped/neutral", re.IGNORECASE)
_WAIT_BOUND = re.compile(r"8\s*h(?:our)?s?|expiresAt|deadline", re.IGNORECASE)
_SUBSCRIBE_OR_BACKOFF = re.compile(
    r"subscribe_github_ci|backoff",
    re.IGNORECASE,
)
_FAIL_CLOSED = re.compile(r"do not merge|fail closed", re.IGNORECASE)


def _policy_forbids_auto_merge(text: str) -> bool:
    """True only when forbid phrasing is present, not mere token presence."""
    if _ALWAYS_PASS_AUTO.search(text):
        return False
    return bool(_NEVER_ENABLE.search(text) and _DO_NOT_PASS_AUTO.search(text) and _AUTO_MERGE_API.search(text))


def _policy_forbids_skipping_failed_or_pending(text: str) -> bool:
    lowered = text.lower()
    if "failed" not in lowered or "pending" not in lowered:
        return False
    if not _SKIP_FAILED_BAN.search(text):
        return False
    if "high-confidence" in lowered and "cannot" not in lowered:
        return False
    return bool(_PLATFORM_SKIP.search(text))


def _policy_bounds_watch_wait(text: str) -> bool:
    return bool(_WAIT_BOUND.search(text) and _SUBSCRIBE_OR_BACKOFF.search(text) and _FAIL_CLOSED.search(text))


def test_base_loadout_includes_no_auto_merge_rule() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    assert RULE_SRC in {entry["src"] for entry in loadout.rules}


def test_no_auto_merge_rule_forbids_auto_and_waits_for_every_check() -> None:
    path = REPO / RULE_SRC
    text = path.read_text()
    meta = parse_rule(path, text)
    assert meta.always_apply is True
    lowered = text.lower()
    assert "never enable auto-merge" in lowered
    assert "do not pass `--auto`" in lowered
    assert "enablepullrequestautomerge" in lowered or "auto-merge api" in lowered
    assert "every attached check" in lowered or "every currently attached check" in lowered
    assert "required-check" in lowered or "branch protection" in lowered
    assert "only when the user asked" in lowered
    assert _policy_forbids_auto_merge(text)
    assert _policy_bounds_watch_wait(text)


def test_no_auto_merge_rule_forbids_skipping_failed_or_pending_checks() -> None:
    text = (REPO / RULE_SRC).read_text()
    assert _policy_forbids_skipping_failed_or_pending(text)
    lowered = text.lower()
    assert "failed" in lowered
    assert "pending" in lowered
    assert "cancelled" in lowered or "canceled" in lowered
    assert "timed-out" in lowered or "timed out" in lowered
    if "high-confidence" in lowered:
        assert "cannot" in lowered or "not skippable" in lowered


def test_no_auto_merge_contract_rejects_enable_auto_wording() -> None:
    """A body that keeps --auto / auto-merge tokens but instructs enabling fails."""
    bad = ENABLE_AUTO_COUNTEREXAMPLE
    assert "--auto" in bad
    assert "auto-merge" in bad.lower()
    assert not _policy_forbids_auto_merge(bad)
    assert not _policy_forbids_skipping_failed_or_pending(bad)
    source = (REPO / RULE_SRC).read_text()
    assert _policy_forbids_auto_merge(source)


def test_base_sync_vendors_no_auto_merge_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [base]\n")
    sync(project)
    dest = project / RULE_DEST
    assert dest.is_file()
    vendored = dest.read_text()
    assert "alwaysApply: true" in vendored
    assert _policy_forbids_auto_merge(vendored)
    assert _policy_forbids_skipping_failed_or_pending(vendored)
    assert _policy_bounds_watch_wait(vendored)
    local_text = (REPO / RULE_DEST).read_text()
    assert _policy_forbids_auto_merge(local_text)
    assert _policy_forbids_skipping_failed_or_pending(local_text)
    assert _policy_bounds_watch_wait(local_text)
