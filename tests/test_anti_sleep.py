"""Contracts for the anti-sleep skill and keep-awake helper."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO / "skills" / "anti-sleep"
SCRIPT = SKILL_ROOT / "scripts" / "keep-awake"
SKILL_MD = SKILL_ROOT / "SKILL.md"


def _run(
    tmp_path: Path,
    *args: str,
    extra_path: Path | None = None,
) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["TMPDIR"] = str(tmp_path)
    if extra_path is not None:
        env["PATH"] = f"{extra_path}{os.pathsep}{env.get('PATH', '')}"
    completed = subprocess.run(
        [str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _darwin_bin(tmp_path: Path) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    args_file = tmp_path / "caffeinate.args"
    (bindir / "uname").write_text('#!/bin/sh\n[ "$1" = "-s" ] && { echo Darwin; exit 0; }\nexec /usr/bin/uname "$@"\n')
    (bindir / "caffeinate").write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" > "{args_file}"\nexec sleep 999\n')
    for name in ("uname", "caffeinate"):
        (bindir / name).chmod(0o755)
    return bindir


def _pidfile(tmp_path: Path) -> Path:
    return tmp_path / f"loadout-anti-sleep.{os.getuid()}.pid"


def _wait_file(path: Path, timeout: float = 1.0) -> Path:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size > 0:
            return path
        time.sleep(0.01)
    raise AssertionError(f"timed out waiting for {path}")


def test_keep_awake_script_is_executable() -> None:
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)


def test_keep_awake_is_noop_on_non_darwin(tmp_path: Path) -> None:
    code, stdout, stderr = _run(tmp_path, "start")
    assert code == 0
    assert "not macOS" in stdout
    assert "Darwin" not in stdout
    assert stderr == ""
    assert not _pidfile(tmp_path).exists()


def test_keep_awake_start_on_darwin_launches_idle_assertion(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    code, stdout, _stderr = _run(tmp_path, "start", "120", extra_path=bindir)
    try:
        assert code == 0
        assert "started" in stdout
        args = _wait_file(tmp_path / "caffeinate.args").read_text()
        assert "-i" in args.split()
        assert "-t" in args.split()
        assert "120" in args.split()
        assert "-d" not in args.split()
        pid = int(_pidfile(tmp_path).read_text().strip())
        os.kill(pid, 0)
    finally:
        _run(tmp_path, "stop", extra_path=bindir)


def test_keep_awake_start_is_idempotent_when_already_running(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    _run(tmp_path, "start", "120", extra_path=bindir)
    try:
        first_pid = _pidfile(tmp_path).read_text().strip()
        code, stdout, _stderr = _run(tmp_path, "start", "120", extra_path=bindir)
        assert code == 0
        assert "already running" in stdout
        assert _pidfile(tmp_path).read_text().strip() == first_pid
    finally:
        _run(tmp_path, "stop", extra_path=bindir)


def test_keep_awake_stop_kills_caffeinate(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    _run(tmp_path, "start", "120", extra_path=bindir)
    pid = int(_pidfile(tmp_path).read_text().strip())
    code, stdout, _stderr = _run(tmp_path, "stop", extra_path=bindir)
    assert code == 0
    assert "stopped" in stdout
    assert not _pidfile(tmp_path).exists()
    time.sleep(0.05)
    with pytest.raises(OSError):
        os.kill(pid, 0)


def test_keep_awake_status_exits_nonzero_when_not_running(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    code, _stdout, stderr = _run(tmp_path, "status", extra_path=bindir)
    assert code == 1
    assert "not running" in stderr


def test_keep_awake_renew_replaces_the_running_process(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    _run(tmp_path, "start", "120", extra_path=bindir)
    try:
        old_pid = int(_pidfile(tmp_path).read_text().strip())
        code, stdout, _stderr = _run(tmp_path, "renew", "90", extra_path=bindir)
        assert code == 0
        new_pid = int(_pidfile(tmp_path).read_text().strip())
        assert new_pid != old_pid
        os.kill(new_pid, 0)
        time.sleep(0.05)
        with pytest.raises(OSError):
            os.kill(old_pid, 0)
        assert "renewed" in stdout
        args = _wait_file(tmp_path / "caffeinate.args").read_text().split()
        assert "90" in args
    finally:
        _run(tmp_path, "stop", extra_path=bindir)


def test_keep_awake_unknown_command_exits_nonzero(tmp_path: Path) -> None:
    code, _stdout, stderr = _run(tmp_path, "jiggle")
    assert code == 2
    assert "usage" in stderr


def test_skill_forbids_per_wait_wraps_and_shell_pid_wait() -> None:
    text = SKILL_MD.read_text()
    lowered = text.lower()
    assert "keep-awake start" in lowered
    assert "caffeinate -w $$" in text or "caffeinate -w $ $" in text or "-w $$" in text
    assert "do not wrap" in lowered or "don't wrap" in lowered
    assert "idle" in lowered
    assert "/anti-sleep" in lowered or "/anti-sleep" in text


def test_skill_forbids_sudo_pmset_and_display_keep_awake() -> None:
    text = SKILL_MD.read_text().lower()
    assert "pmset" in text
    assert "disablesleep" in text
    assert "sudo" in text
    assert "-d" in text
    assert "lid" in text


def test_base_loadout_includes_anti_sleep() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert "skills/anti-sleep" in srcs


def test_anti_sleep_evals_exist() -> None:
    evals = SKILL_ROOT / "evals" / "evals.json"
    assert evals.is_file()
    data = evals.read_text()
    assert '"skill_name": "anti-sleep"' in data
    assert "keep-awake" in data
