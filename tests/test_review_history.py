"""Retention trim for REVIEW_HISTORY.md (entries older than 30 days)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "skills" / "log-progress" / "scripts" / "trim_review_history.py"
NOW = datetime(2026, 9, 2, tzinfo=UTC)

PREAMBLE = """# Review history

Append-only log for the PR-review harness. Do not rewrite.

"""

OLD_ENTRY = """## 2026-07-24T00:00:00Z — review_orchestrator — panel

- **Task:** none
- **Outcome:** ok
- **Summary:** Forty days old.

"""

EXACT_ENTRY = """## 2026-08-03T00:00:00Z — review_orchestrator — verify

- **Task:** none
- **Outcome:** ok
- **Summary:** Exactly thirty days old.

"""

RECENT_ENTRY = """## 2026-09-01T12:00:00Z — review_orchestrator — decision

- **Task:** none
- **Outcome:** ok
- **Summary:** Yesterday.

"""

UNPARSEABLE_ENTRY = """## yesterday — review_orchestrator — panel

- **Task:** none
- **Outcome:** ok
- **Summary:** Timestamp is not ISO.

"""


def _load_script() -> ModuleType:
    assert SCRIPT.is_file(), SCRIPT
    spec = importlib.util.spec_from_file_location("trim_review_history", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_trim_drops_only_entries_older_than_30_days() -> None:
    module = _load_script()
    text = PREAMBLE + OLD_ENTRY + EXACT_ENTRY + RECENT_ENTRY
    trimmed = module.trim_review_history(text, now=NOW)
    assert "Forty days old." not in trimmed
    assert "Exactly thirty days old." in trimmed
    assert "Yesterday." in trimmed
    assert trimmed.startswith("# Review history")


def test_trim_keeps_unparseable_entry_timestamps() -> None:
    module = _load_script()
    text = PREAMBLE + UNPARSEABLE_ENTRY + OLD_ENTRY
    trimmed = module.trim_review_history(text, now=NOW)
    assert "Timestamp is not ISO." in trimmed
    assert "Forty days old." not in trimmed


def test_trim_file_is_noop_when_history_is_missing(tmp_path: Path) -> None:
    module = _load_script()
    missing = tmp_path / "REVIEW_HISTORY.md"
    module.trim_review_history_file(missing, now=NOW)
    assert not missing.exists()


def test_trim_cli_rewrites_cwd_review_history(tmp_path: Path) -> None:
    ancient = """## 2020-01-01T00:00:00Z — review_orchestrator — panel

- **Summary:** Ancient.

"""
    far_future = """## 2099-01-01T00:00:00Z — review_orchestrator — decision

- **Summary:** Far future.

"""
    history = tmp_path / "REVIEW_HISTORY.md"
    history.write_text(PREAMBLE + ancient + far_future, encoding="utf-8")
    subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp_path, check=True)
    trimmed = history.read_text(encoding="utf-8")
    assert "Ancient." not in trimmed
    assert "Far future." in trimmed
