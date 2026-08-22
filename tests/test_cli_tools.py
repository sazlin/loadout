from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from loadout.cli_tools import run_cli_tools
from loadout.models import CliTool


def test_run_cli_tools_executes_commands_in_the_project_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    marker = tmp_path / "installed.txt"
    tools = [CliTool(name="marker", command=f"echo ok > {marker.name}")]

    run_cli_tools(tools, tmp_path)

    assert marker.read_text() == "ok\n"
    output = capsys.readouterr().out
    assert "loadout: cli_tools: marker: running" in output
    assert "loadout: cli_tools: marker: ok" in output


def test_run_cli_tools_continues_after_a_failed_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    tools = [
        CliTool(name="first", command=f"echo first > {first.name}"),
        CliTool(name="boom", command="echo boom-stderr >&2; exit 7"),
        CliTool(name="second", command=f"echo second > {second.name}"),
    ]

    run_cli_tools(tools, tmp_path)

    assert first.read_text() == "first\n"
    assert second.read_text() == "second\n"
    captured = capsys.readouterr()
    assert "loadout: cli_tools: boom: failed (exit 7)" in captured.out
    assert "boom-stderr" in captured.err


def test_run_cli_tools_reports_commands_that_fail_to_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def explode(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise FileNotFoundError("bash")

    monkeypatch.setattr("loadout.cli_tools.subprocess.Popen", explode)

    run_cli_tools([CliTool(name="jq", command="true")], tmp_path)

    output = capsys.readouterr().out
    assert "loadout: cli_tools: jq: failed to start" in output


def test_run_cli_tools_noops_when_the_list_is_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_cli_tools([], tmp_path)

    assert capsys.readouterr().out == ""
    assert list(tmp_path.iterdir()) == []


def test_run_cli_tools_times_out_a_hung_command_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("loadout.cli_tools._CLI_TOOL_TIMEOUT_SECONDS", 0.4)
    later = tmp_path / "later.txt"
    grandchild_pid = tmp_path / "grandchild.pid"
    tools = [
        CliTool(
            name="hung",
            command=f"sleep 8 & echo $! > {grandchild_pid.name}; wait",
        ),
        CliTool(name="later", command=f"echo later > {later.name}"),
    ]

    run_cli_tools(tools, tmp_path)

    assert later.read_text() == "later\n"
    output = capsys.readouterr().out
    assert "loadout: cli_tools: hung: failed (timeout" in output
    assert "loadout: cli_tools: later: ok" in output
    pid = int(grandchild_pid.read_text())
    with pytest.raises(OSError):
        os.kill(pid, 0)


def test_run_cli_tools_kills_process_group_on_keyboard_interrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    grandchild_pid = tmp_path / "grandchild.pid"
    original_communicate = subprocess.Popen.communicate
    waiting_for_interrupt = True

    def communicate_then_interrupt(
        self: subprocess.Popen[str], input: str | None = None, timeout: float | None = None
    ) -> tuple[str, str]:
        nonlocal waiting_for_interrupt
        if waiting_for_interrupt:
            deadline = time.monotonic() + 2
            while not grandchild_pid.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            waiting_for_interrupt = False
            raise KeyboardInterrupt
        return original_communicate(self, input, timeout)

    monkeypatch.setattr(subprocess.Popen, "communicate", communicate_then_interrupt)
    tools = [
        CliTool(
            name="hung",
            command=f"sleep 8 & echo $! > {grandchild_pid.name}; wait",
        ),
    ]

    try:
        with pytest.raises(KeyboardInterrupt):
            run_cli_tools(tools, tmp_path)
        pid = int(grandchild_pid.read_text())
        deadline = time.monotonic() + 2
        while True:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            if time.monotonic() >= deadline:
                pytest.fail(f"cli_tools grandchild {pid} still running after cancel")
            time.sleep(0.05)
    finally:
        if grandchild_pid.exists():
            leftover = int(grandchild_pid.read_text())
            try:
                os.kill(leftover, signal.SIGKILL)
            except OSError:
                pass
