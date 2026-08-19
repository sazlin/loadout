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


def _env(tmp_path: Path, extra_path: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["TMPDIR"] = str(tmp_path)
    if extra_path is not None:
        env["PATH"] = f"{extra_path}{os.pathsep}{env.get('PATH', '')}"
    return env


def _run(
    tmp_path: Path,
    *args: str,
    extra_path: Path | None = None,
) -> tuple[int, str, str]:
    completed = subprocess.run(
        [str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        env=_env(tmp_path, extra_path),
    )
    return completed.returncode, completed.stdout, completed.stderr


def _uname_bin(tmp_path: Path, *, system: str) -> Path:
    bindir = tmp_path / f"bin-{system.lower()}"
    bindir.mkdir()
    # Never fall through to the host uname; tests must not depend on the machine OS.
    (bindir / "uname").write_text(f'#!/bin/sh\n[ "$1" = "-s" ] && {{ echo "{system}"; exit 0; }}\nexit 1\n')
    (bindir / "uname").chmod(0o755)
    return bindir


def _darwin_bin(tmp_path: Path) -> Path:
    bindir = _uname_bin(tmp_path, system="Darwin")
    args_file = tmp_path / "caffeinate.args"
    # Stay in-process so ps args still name this stub and include -i.
    (bindir / "caffeinate").write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "import time\n"
        f"open({str(args_file)!r}, 'w', encoding='utf-8').write(' '.join(sys.argv[1:]) + '\\n')\n"
        "time.sleep(999)\n"
    )
    (bindir / "caffeinate").chmod(0o755)
    return bindir


def _pidfile(tmp_path: Path) -> Path:
    return tmp_path / "Library" / "Caches" / "loadout-anti-sleep" / "keep-awake.pid"


def _prepare_pidfile(tmp_path: Path, contents: str) -> Path:
    pidfile = _pidfile(tmp_path)
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.parent.chmod(0o700)
    pidfile.write_text(contents)
    return pidfile


def _wait_file(path: Path, timeout: float = 1.0) -> Path:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size > 0:
            return path
        time.sleep(0.01)
    raise AssertionError(f"timed out waiting for {path}")


def _keeper_pids(bindir: Path) -> list[int]:
    needle = str(bindir / "caffeinate")
    listed = subprocess.run(
        ["ps", "-ww", "-eo", "pid=,args="],
        check=True,
        capture_output=True,
        text=True,
    )
    pids: list[int] = []
    for line in listed.stdout.splitlines():
        stripped = line.strip()
        if needle not in stripped:
            continue
        pid_str, _, args = stripped.partition(" ")
        if " -i " not in f" {args} ":
            continue
        pids.append(int(pid_str))
    return pids


def test_keep_awake_script_is_executable() -> None:
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)


def test_keep_awake_is_noop_on_non_darwin(tmp_path: Path) -> None:
    bindir = _uname_bin(tmp_path, system="Linux")
    uname_s = subprocess.run(
        [str(bindir / "uname"), "-s"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert uname_s == "Linux"
    # Shadow host caffeinate so a failed no-op cannot start a real keeper.
    invoked = tmp_path / "caffeinate.invoked"
    trap = bindir / "caffeinate"
    trap.write_text(f"#!/bin/sh\nprintf 'invoked\\n' > {str(invoked)!r}\nexit 1\n")
    trap.chmod(0o755)
    try:
        code, stdout, stderr = _run(tmp_path, "start", extra_path=bindir)
        assert code == 0
        assert "not macOS" in stdout
        assert "Linux" in stdout
        assert "Darwin" not in stdout
        assert stderr == ""
        assert not _pidfile(tmp_path).exists()
        assert not invoked.exists()
    finally:
        _run(tmp_path, "stop", extra_path=bindir)


def test_keep_awake_start_on_darwin_launches_idle_assertion(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    code, stdout, _stderr = _run(tmp_path, "start", "120", extra_path=bindir)
    try:
        assert code == 0
        assert "started" in stdout
        args = _wait_file(tmp_path / "caffeinate.args").read_text().split()
        assert args == ["-i", "-t", "120"]
        pid = int(_pidfile(tmp_path).read_text().strip())
        os.kill(pid, 0)
        cache_dir = _pidfile(tmp_path).parent
        assert cache_dir.name == "loadout-anti-sleep"
        assert cache_dir.stat().st_mode & 0o777 == 0o700
        assert not (tmp_path / f"loadout-anti-sleep.{os.getuid()}.pid").exists()
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
        assert args == ["-i", "-t", "90"]
    finally:
        _run(tmp_path, "stop", extra_path=bindir)


def test_status_treats_live_non_caffeinate_pidfile_as_not_running(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    sleeper = subprocess.Popen(["sleep", "60"])
    try:
        _prepare_pidfile(tmp_path, f"{sleeper.pid}\n")
        code, _stdout, stderr = _run(tmp_path, "status", extra_path=bindir)
        assert code == 1
        assert "not running" in stderr
        assert sleeper.poll() is None
        assert not _pidfile(tmp_path).exists()
    finally:
        sleeper.kill()
        sleeper.wait()


def test_start_launches_when_pidfile_points_at_live_sleep(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    sleeper = subprocess.Popen(["sleep", "60"])
    try:
        _prepare_pidfile(tmp_path, f"{sleeper.pid}\n")
        code, stdout, _stderr = _run(tmp_path, "start", "120", extra_path=bindir)
        assert code == 0
        assert "started" in stdout
        keeper = int(_pidfile(tmp_path).read_text().strip())
        assert keeper != sleeper.pid
        os.kill(keeper, 0)
        assert sleeper.poll() is None
    finally:
        sleeper.kill()
        sleeper.wait()
        _run(tmp_path, "stop", extra_path=bindir)


def test_stop_does_not_signal_live_non_caffeinate_pid(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    sleeper = subprocess.Popen(["sleep", "60"])
    try:
        _prepare_pidfile(tmp_path, f"{sleeper.pid}\n")
        code, stdout, _stderr = _run(tmp_path, "stop", extra_path=bindir)
        assert code == 0
        assert "not running" in stdout
        assert sleeper.poll() is None
        os.kill(sleeper.pid, 0)
        assert not _pidfile(tmp_path).exists()
    finally:
        sleeper.kill()
        sleeper.wait()


@pytest.mark.parametrize("contents", ["0", "-9", "--1"])
def test_stop_ignores_non_positive_pidfile_contents(tmp_path: Path, contents: str) -> None:
    bindir = _darwin_bin(tmp_path)
    sleeper = subprocess.Popen(["sleep", "60"])
    try:
        _prepare_pidfile(tmp_path, f"{contents}\n")
        code, stdout, _stderr = _run(tmp_path, "stop", extra_path=bindir)
        assert code == 0
        assert "not running" in stdout
        assert sleeper.poll() is None
        assert not _pidfile(tmp_path).exists()
    finally:
        sleeper.kill()
        sleeper.wait()


def test_renew_does_not_signal_live_non_caffeinate_pid(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    sleeper = subprocess.Popen(["sleep", "60"])
    try:
        _prepare_pidfile(tmp_path, f"{sleeper.pid}\n")
        code, stdout, _stderr = _run(tmp_path, "renew", "90", extra_path=bindir)
        assert code == 0
        assert "renewed" in stdout
        assert sleeper.poll() is None
        keeper = int(_pidfile(tmp_path).read_text().strip())
        assert keeper != sleeper.pid
    finally:
        sleeper.kill()
        sleeper.wait()
        _run(tmp_path, "stop", extra_path=bindir)


def test_start_does_not_follow_pidfile_symlink(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    target = tmp_path / "clobber_me"
    target.write_text("secret\n")
    pidfile = _pidfile(tmp_path)
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.parent.chmod(0o700)
    pidfile.symlink_to(target)
    try:
        code, stdout, _stderr = _run(tmp_path, "start", "120", extra_path=bindir)
        assert code == 0
        assert "started" in stdout
        assert target.read_text() == "secret\n"
        assert pidfile.is_file()
        assert not pidfile.is_symlink()
        int(pidfile.read_text().strip())
    finally:
        _run(tmp_path, "stop", extra_path=bindir)


def test_overlapping_starts_leave_one_keeper(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    env = _env(tmp_path, extra_path=bindir)
    procs = [
        subprocess.Popen(
            [str(SCRIPT), "start", "120"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    results = [proc.communicate(timeout=10) for proc in procs]
    try:
        assert [proc.returncode for proc in procs] == [0, 0]
        texts = [stdout for stdout, _stderr in results]
        assert sum("started" in text for text in texts) == 1
        assert sum("already running" in text for text in texts) == 1
        keeper = int(_wait_file(_pidfile(tmp_path)).read_text().strip())
        os.kill(keeper, 0)
        assert set(_keeper_pids(bindir)) == {keeper}
    finally:
        _run(tmp_path, "stop", extra_path=bindir)


def test_overlapping_renews_leave_one_keeper(tmp_path: Path) -> None:
    bindir = _darwin_bin(tmp_path)
    _run(tmp_path, "start", "120", extra_path=bindir)
    env = _env(tmp_path, extra_path=bindir)
    procs = [
        subprocess.Popen(
            [str(SCRIPT), "renew", "90"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    results = [proc.communicate(timeout=10) for proc in procs]
    try:
        assert [proc.returncode for proc in procs] == [0, 0]
        assert all("renewed" in stdout for stdout, _stderr in results)
        keeper = int(_wait_file(_pidfile(tmp_path)).read_text().strip())
        os.kill(keeper, 0)
        assert set(_keeper_pids(bindir)) == {keeper}
        _run(tmp_path, "stop", extra_path=bindir)
        assert not _pidfile(tmp_path).exists()
        time.sleep(0.05)
        with pytest.raises(OSError):
            os.kill(keeper, 0)
    finally:
        _run(tmp_path, "stop", extra_path=bindir)


def test_keep_awake_script_never_uses_sudo_or_pmset_writes() -> None:
    text = SCRIPT.read_text()
    assert "sudo" not in text
    assert "disablesleep" not in text
    assert "pmset -a" not in text
    assert "pmset -b" not in text
    assert "pmset -c" not in text
    assert "pmset -g assertions" in text


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
