#!/usr/bin/env python3
"""Run resolve-wave git with list argv (no shell interpolation).

`add` JSON `isolated` means the checkout exists; it does not copy tasks_path.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

TASK_ID_RE = re.compile(r"^TASK-[0-9]+$")
TASK_BRANCH_SUFFIX_RE = re.compile(r"-TASK-[0-9]+$")
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
_DEFAULT_GIT_TIMEOUT_SECONDS = 120
_GIT_TIMEOUT_ENV = "LOADOUT_GIT_TIMEOUT_SECONDS"
USAGE = """usage:
  prepare_wave_worktrees.py add --pr-head <ref> <wave-json>
  prepare_wave_worktrees.py cherry-pick --task-branch <branch> [--] <sha>
  prepare_wave_worktrees.py push --task-branch <branch>
  prepare_wave_worktrees.py prune --pr-head <ref> <wave-json>"""


def worktree_relpath(pr_head: str, task_id: str) -> Path:
    """Return `.worktrees/<slash-flattened-head>-<TASK-ID>` (one extra segment)."""
    return Path(".worktrees") / f"{pr_head.replace('/', '-')}-{task_id}"


def _usage() -> int:
    print(USAGE, file=sys.stderr)
    return 2


def _git_timeout_seconds() -> float:
    override = os.environ.get(_GIT_TIMEOUT_ENV)
    if override is not None and override.strip():
        return float(override)
    return _DEFAULT_GIT_TIMEOUT_SECONDS


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    command = ["git", *args]
    timeout = _git_timeout_seconds()
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        process = getattr(error, "process", None)
        if process is not None:
            process.kill()
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr=f"Git command timed out after {timeout}s",
        )


def _reject_unsafe_token(value: str, kind: str) -> str | None:
    if not value or value.strip() != value:
        return f"invalid {kind}"
    if value.startswith("-"):
        return f"{kind} must not start with '-'"
    if ";" in value or "$(" in value or "`" in value or "\n" in value:
        return f"{kind} contains unsafe characters"
    return None


def _normalize_head_ref(pr_head: str) -> str | None:
    err = _reject_unsafe_token(pr_head, "pr-head")
    if err is not None:
        print(f"error: {err}", file=sys.stderr)
        return None
    proc = _run_git(["check-ref-format", "--normalize", f"refs/heads/{pr_head}"])
    if proc.returncode != 0:
        print(f"error: invalid pr-head ref: {pr_head}", file=sys.stderr)
        return None
    normalized = proc.stdout.strip()
    prefix = "refs/heads/"
    if normalized.startswith(prefix):
        return normalized[len(prefix) :]
    return normalized or pr_head


def _normalize_branch(branch: str) -> str | None:
    err = _reject_unsafe_token(branch, "branch")
    if err is not None:
        print(f"error: {err}", file=sys.stderr)
        return None
    if not TASK_BRANCH_SUFFIX_RE.search(branch):
        print("error: branch must end with -TASK-<digits>", file=sys.stderr)
        return None
    proc = _run_git(["check-ref-format", "--normalize", f"refs/heads/{branch}"])
    if proc.returncode != 0:
        print(f"error: invalid branch: {branch}", file=sys.stderr)
        return None
    prefix = "refs/heads/"
    normalized = proc.stdout.strip()
    if normalized.startswith(prefix):
        return normalized[len(prefix) :]
    return normalized or branch


def _parse_wave(raw: str) -> list[str] | None:
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError:
        print("error: wave JSON is malformed", file=sys.stderr)
        return None
    ids = payload.get("wave") if isinstance(payload, dict) else payload
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        print('error: wave JSON must be {"wave": ["TASK-001", ...]}', file=sys.stderr)
        return None
    for task_id in ids:
        if TASK_ID_RE.fullmatch(task_id) is None:
            print(f"error: invalid task id: {task_id}", file=sys.stderr)
            return None
    return ids


def _option_and_positional(args: list[str], flag: str) -> tuple[str | None, list[str], bool]:
    value: str | None = None
    positional: list[str] = []
    i = 0
    missing_value = False
    while i < len(args):
        if args[i] == "--":
            positional.extend(args[i + 1 :])
            break
        if args[i] == flag:
            if i + 1 >= len(args):
                missing_value = True
                break
            value = args[i + 1]
            i += 2
            continue
        positional.append(args[i])
        i += 1
    return value, positional, missing_value


def _pr_head_from_args(args: list[str]) -> tuple[str | None, list[str]] | int:
    pr_head, positional, missing = _option_and_positional(args, "--pr-head")
    if missing:
        return _usage()
    if pr_head is None:
        pr_head = os.environ.get("PR_HEAD_REF")
    if not pr_head or len(positional) != 1:
        return _usage()
    return pr_head, positional


def _head_sha() -> str | None:
    proc = _run_git(["rev-parse", "HEAD"])
    sha = proc.stdout.strip()
    if proc.returncode != 0 or SHA_RE.fullmatch(sha) is None:
        print("error: could not resolve HEAD", file=sys.stderr)
        return None
    return sha


def _reset_to_head(path: Path, head: str) -> bool:
    proc = _run_git(["-C", str(path), "reset", "--hard", head])
    return proc.returncode == 0


def _worktree_registered(path: Path) -> bool:
    listed = _run_git(["worktree", "list", "--porcelain"])
    if listed.returncode != 0:
        return False
    want = path.resolve()
    prefix = "worktree "
    for line in listed.stdout.splitlines():
        if not line.startswith(prefix):
            continue
        if Path(line[len(prefix) :]).resolve() == want:
            return True
    return False


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink(missing_ok=True)


def _worktree_add(path: Path, branch: str) -> bool:
    created = _run_git(["worktree", "add", "-b", branch, str(path), "HEAD"])
    if created.returncode == 0:
        return True
    existing = _run_git(["worktree", "add", str(path), branch])
    return existing.returncode == 0


def _reuse_or_add(path: Path, branch: str, head: str) -> bool:
    if _worktree_registered(path):
        if _reset_to_head(path, head):
            return True
    elif path.exists():
        _remove_path(path)
    return _worktree_add(path, branch)


def _ensure_task(pr_head: str, task_id: str, head: str) -> dict[str, Any]:
    branch = f"{pr_head}-{task_id}"
    rel = worktree_relpath(pr_head, task_id)
    tmp = Path("/tmp") / f"pr-resolve-{task_id}"
    if _reuse_or_add(rel, branch, head):
        return {"id": task_id, "branch": branch, "worktree": str(rel), "isolated": True}
    if _reuse_or_add(tmp, branch, head):
        return {"id": task_id, "branch": branch, "worktree": str(tmp), "isolated": True}
    _run_git(["branch", branch])
    return {"id": task_id, "branch": branch, "worktree": None, "isolated": False}


def _cmd_add(args: list[str]) -> int:
    parsed = _pr_head_from_args(args)
    if isinstance(parsed, int):
        return parsed
    pr_head_raw, positional = parsed
    pr_head = _normalize_head_ref(pr_head_raw)
    if pr_head is None:
        return 2
    ids = _parse_wave(positional[0])
    if ids is None:
        return 2
    head = _head_sha()
    if head is None:
        return 2
    tasks = [_ensure_task(pr_head, task_id, head) for task_id in ids]
    print(json.dumps({"pr_head": pr_head, "tasks": tasks}))
    return 0


def _validate_sha(sha: str) -> bool:
    if _reject_unsafe_token(sha, "sha") is not None or SHA_RE.fullmatch(sha) is None:
        print("error: cherry-pick SHA must be 7-40 lowercase hex", file=sys.stderr)
        return False
    return True


def _sha_on_fetched_tip(sha: str) -> bool:
    contained = _run_git(["merge-base", "--is-ancestor", sha, "FETCH_HEAD"])
    return contained.returncode == 0


def _cmd_cherry_pick(args: list[str]) -> int:
    branch_raw, positional, missing = _option_and_positional(args, "--task-branch")
    if missing or branch_raw is None or len(positional) != 1:
        return _usage()
    branch = _normalize_branch(branch_raw)
    if branch is None:
        return 2
    sha = positional[0]
    if not _validate_sha(sha):
        return 2
    refspec = f"+refs/heads/{branch}:refs/remotes/origin/{branch}"
    fetched = _run_git(["fetch", "origin", refspec])
    if fetched.returncode != 0:
        err = (fetched.stderr or fetched.stdout).strip()
        print(err or "error: git fetch failed", file=sys.stderr)
        return 1
    if not _sha_on_fetched_tip(sha):
        print("error: SHA is not on the task branch", file=sys.stderr)
        return 2
    picked = _run_git(["cherry-pick", "--", sha])
    if picked.returncode != 0:
        _run_git(["cherry-pick", "--abort"])
        err = (picked.stderr or picked.stdout).strip()
        print(err or "error: cherry-pick failed", file=sys.stderr)
        return 1
    return 0


def _cmd_push(args: list[str]) -> int:
    branch_raw, positional, missing = _option_and_positional(args, "--task-branch")
    if missing or branch_raw is None or positional:
        return _usage()
    branch = _normalize_branch(branch_raw)
    if branch is None:
        return 2
    pushed = _run_git(["push", "--", "origin", branch])
    if pushed.returncode != 0:
        err = (pushed.stderr or pushed.stdout).strip()
        print(err or "error: git push failed", file=sys.stderr)
        return 1
    return 0


def _cmd_prune(args: list[str]) -> int:
    parsed = _pr_head_from_args(args)
    if isinstance(parsed, int):
        return parsed
    pr_head_raw, positional = parsed
    pr_head = _normalize_head_ref(pr_head_raw)
    if pr_head is None:
        return 2
    ids = _parse_wave(positional[0])
    if ids is None:
        return 2
    for task_id in ids:
        rel = worktree_relpath(pr_head, task_id)
        tmp = Path("/tmp") / f"pr-resolve-{task_id}"
        _run_git(["worktree", "remove", "--force", str(rel)])
        _run_git(["worktree", "remove", "--force", str(tmp)])
        _run_git(["branch", "-D", f"{pr_head}-{task_id}"])
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    _run_git(["worktree", "prune"])
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch add / cherry-pick / push / prune. Returns 2 on usage or validation."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        return _usage()
    cmd, *rest = args
    if cmd == "add":
        return _cmd_add(rest)
    if cmd == "cherry-pick":
        return _cmd_cherry_pick(rest)
    if cmd == "push":
        return _cmd_push(rest)
    if cmd == "prune":
        return _cmd_prune(rest)
    return _usage()


if __name__ == "__main__":
    raise SystemExit(main())
