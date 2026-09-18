"""Argv-safe wave git helper: reject unsafe refs and non-hex SHAs."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "skills" / "dispatch-resolve-wave" / "scripts" / "prepare_wave_worktrees.py"


def _load_script() -> ModuleType:
    assert SCRIPT.is_file(), SCRIPT
    spec = importlib.util.spec_from_file_location("prepare_wave_worktrees", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record_run(monkeypatch: Any) -> list[tuple[list[str], bool]]:
    calls: list[tuple[list[str], bool]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((list(argv), bool(kwargs.get("shell", False))))
        stdout = ""
        if len(argv) >= 2 and argv[1] == "check-ref-format":
            stdout = f"{argv[-1]}\n"
        elif len(argv) >= 2 and argv[1] == "rev-parse":
            stdout = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_semicolon_pr_head_exits_2_without_git_interpolation(monkeypatch: Any) -> None:
    module = _load_script()
    calls = _record_run(monkeypatch)
    rc = module.main(["add", "--pr-head", "evil;rm -rf /", json.dumps({"wave": ["TASK-001"]})])
    assert rc == 2
    captured = " ".join(" ".join(argv) for argv, _ in calls)
    assert "evil;rm -rf /" not in captured
    assert all(not shell for _, shell in calls)
    assert not any("worktree" in argv for argv, _ in calls)


def test_dollar_paren_pr_head_exits_2_without_git_interpolation(monkeypatch: Any) -> None:
    module = _load_script()
    calls = _record_run(monkeypatch)
    rc = module.main(["add", "--pr-head", "feat$(whoami)", json.dumps({"wave": ["TASK-001"]})])
    assert rc == 2
    captured = " ".join(" ".join(argv) for argv, _ in calls)
    assert "feat$(whoami)" not in captured
    assert "$(whoami)" not in captured
    assert all(not shell for _, shell in calls)


def test_non_hex_and_leading_dash_sha_rejected_before_cherry_pick(
    monkeypatch: Any,
) -> None:
    module = _load_script()
    calls = _record_run(monkeypatch)
    range_rc = module.main(["cherry-pick", "--task-branch", "cursor/ok-TASK-001", "HEAD~2..HEAD"])
    dash_rc = module.main(["cherry-pick", "--task-branch", "cursor/ok-TASK-001", "--", "--abort"])
    assert range_rc == 2
    assert dash_rc == 2
    assert not any(
        argv[:2] == ["git", "cherry-pick"] or (len(argv) > 1 and argv[1] == "cherry-pick") for argv, _ in calls
    )


def test_worktree_path_maps_slash_to_single_segment() -> None:
    module = _load_script()
    path = module.worktree_relpath("feature/topic", "TASK-003")
    assert path == Path(".worktrees") / "feature-topic-TASK-003"
    assert path.parts == (".worktrees", "feature-topic-TASK-003")
    assert "/" not in path.name


def test_add_invokes_git_worktree_with_argv_list_no_shell(monkeypatch: Any) -> None:
    module = _load_script()
    calls = _record_run(monkeypatch)
    rc = module.main(
        [
            "add",
            "--pr-head",
            "cursor/feature",
            json.dumps({"wave": ["TASK-001"]}),
        ]
    )
    assert rc == 0
    assert all(not shell for _, shell in calls)
    worktree_add = [argv for argv, _ in calls if argv[:3] == ["git", "worktree", "add"]]
    assert worktree_add
    joined = " ".join(worktree_add[0])
    assert ".worktrees/cursor-feature-TASK-001" in joined
    assert ".worktrees/cursor/feature" not in joined
    assert all(argv[0] == "git" for argv, _ in calls)


def test_add_json_and_docstring_state_isolated_does_not_copy_tasks_path(monkeypatch: Any, capsys: Any) -> None:
    module = _load_script()
    _record_run(monkeypatch)
    rc = module.main(
        [
            "add",
            "--pr-head",
            "cursor/feature",
            json.dumps({"wave": ["TASK-001"]}),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tasks_path_copied"] is False
    doc = (module.__doc__ or "").lower()
    assert "isolated" in doc
    assert "tasks_path" in doc
    assert "does not copy" in doc
