"""Argv-safe wave git helper: reject unsafe refs and non-hex SHAs."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

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


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_sha(cwd: Path, ref: str = "HEAD") -> str:
    return _git(cwd, "rev-parse", ref).stdout.strip()


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "test")
    (path / "file.txt").write_text("base\n")
    _git(path, "add", "file.txt")
    _git(path, "commit", "-m", "init")


def test_cherry_pick_accepts_sha_on_fetched_origin_branch_not_local_head(tmp_path: Path, monkeypatch: Any) -> None:
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(origin))
    consumer = tmp_path / "consumer"
    _init_repo(consumer)
    _git(consumer, "checkout", "-b", "cursor/wave")
    _git(consumer, "remote", "add", "origin", str(origin))
    _git(consumer, "push", "-u", "origin", "cursor/wave")
    task_branch = "cursor/wave-TASK-001"
    _git(consumer, "branch", task_branch)
    _git(consumer, "push", "origin", task_branch)
    local_task_sha = _git_sha(consumer, task_branch)

    resolver = tmp_path / "resolver"
    _git(tmp_path, "clone", str(origin), str(resolver))
    _git(resolver, "config", "user.email", "test@example.com")
    _git(resolver, "config", "user.name", "test")
    _git(resolver, "checkout", "-B", task_branch, f"origin/{task_branch}")
    (resolver / "file.txt").write_text("resolver\n")
    _git(resolver, "add", "file.txt")
    _git(resolver, "commit", "-m", "resolver")
    _git(resolver, "push", "origin", task_branch)
    new_sha = _git_sha(resolver)
    assert _git_sha(consumer, task_branch) == local_task_sha
    assert new_sha != local_task_sha

    monkeypatch.chdir(consumer)
    module = _load_script()
    rc = module.main(["cherry-pick", "--task-branch", task_branch, "--", new_sha])
    assert rc == 0
    assert (consumer / "file.txt").read_text() == "resolver\n"
    assert _git(consumer, "log", "--format=%s", "-1", "HEAD").stdout.strip() == "resolver"


def test_cherry_pick_rejects_sha_not_on_fetched_task_branch(tmp_path: Path, monkeypatch: Any) -> None:
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(origin))
    consumer = tmp_path / "consumer"
    _init_repo(consumer)
    _git(consumer, "checkout", "-b", "cursor/wave")
    _git(consumer, "remote", "add", "origin", str(origin))
    _git(consumer, "push", "-u", "origin", "cursor/wave")
    task_branch = "cursor/wave-TASK-001"
    _git(consumer, "branch", task_branch)
    _git(consumer, "push", "origin", task_branch)
    (consumer / "other.txt").write_text("local-only\n")
    _git(consumer, "add", "other.txt")
    _git(consumer, "commit", "-m", "not on origin task branch")
    foreign_sha = _git_sha(consumer)
    _git(consumer, "reset", "--hard", "HEAD~1")

    monkeypatch.chdir(consumer)
    module = _load_script()
    rc = module.main(["cherry-pick", "--task-branch", task_branch, "--", foreign_sha])
    assert rc == 2
    assert (consumer / "file.txt").read_text() == "base\n"
    assert not (consumer / "other.txt").exists()


def test_add_reuses_leftover_worktree_by_hard_reset_to_pr_head(
    tmp_path: Path, monkeypatch: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    old = _git_sha(repo)
    worktree = repo / ".worktrees" / "cursor-wave-TASK-001"
    _git(repo, "worktree", "add", "-b", "cursor/wave-TASK-001", str(worktree))
    assert _git_sha(worktree) == old
    (repo / "file.txt").write_text("pr-head\n")
    _git(repo, "add", "file.txt")
    _git(repo, "commit", "-m", "pr")
    pr_head = _git_sha(repo)
    assert _git_sha(worktree) == old

    monkeypatch.chdir(repo)
    module = _load_script()
    rc = module.main(["add", "--pr-head", "cursor/wave", json.dumps({"wave": ["TASK-001"]})])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tasks"][0]["isolated"] is True
    assert _git_sha(worktree) == pr_head
    reset = _git(worktree, "rev-parse", "--verify", "HEAD")
    assert reset.stdout.strip() == pr_head


def test_add_does_not_report_plain_leftover_dir_isolated_without_worktree(
    tmp_path: Path, monkeypatch: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    leftover = repo / ".worktrees" / "cursor-wave-TASK-001"
    leftover.mkdir(parents=True)
    (leftover / "stale.txt").write_text("not a worktree\n")

    monkeypatch.chdir(repo)
    module = _load_script()
    rc = module.main(["add", "--pr-head", "cursor/wave", json.dumps({"wave": ["TASK-001"]})])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    task = payload["tasks"][0]
    git_dir = subprocess.run(
        ["git", "-C", str(leftover), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    if git_dir.returncode != 0:
        assert task["isolated"] is False
    else:
        assert task["isolated"] is True
        assert not (leftover / "stale.txt").exists()
        listed = _git(repo, "worktree", "list", "--porcelain").stdout
        assert str(leftover.resolve()) in listed


def test_run_git_timeout_is_nonzero_without_hanging(monkeypatch: Any) -> None:
    monkeypatch.setenv("LOADOUT_GIT_TIMEOUT_SECONDS", "0.2")
    module = _load_script()

    def hang(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        timeout = kwargs.get("timeout")
        assert timeout is not None
        assert kwargs.get("shell") is False
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr(subprocess, "run", hang)
    proc = module._run_git(["fetch", "origin", "cursor/ok-TASK-001"])
    assert proc.returncode != 0


def test_cherry_pick_and_push_timeout_exit_nonzero(monkeypatch: Any) -> None:
    module = _load_script()

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert kwargs.get("shell") is False
        if len(argv) >= 2 and argv[1] == "check-ref-format":
            return subprocess.CompletedProcess(argv, 0, stdout=f"{argv[-1]}\n", stderr="")
        if "fetch" in argv or "push" in argv:
            raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout") or 120)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    pick_rc = module.main(["cherry-pick", "--task-branch", "cursor/ok-TASK-001", "aaaaaaaaaaaaaaaa"])
    push_rc = module.main(["push", "--task-branch", "cursor/ok-TASK-001"])
    assert pick_rc == 1
    assert push_rc == 1
