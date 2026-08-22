"""Run loadout-declared CLI install commands. Failures are reported, never fatal."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import TextIO

from loadout.models import CliTool

_SHELL = ("bash", "-c")
_CLI_TOOL_TIMEOUT_SECONDS = 300


def run_cli_tools(tools: list[CliTool], project_root: Path) -> None:
    """Run each command in ``project_root``. Continue after failures."""
    sys.stdout.flush()
    sys.stderr.flush()
    for tool in tools:
        _run_one(tool, project_root)


def _run_one(tool: CliTool, project_root: Path) -> None:
    print(f"loadout: cli_tools: {tool.name}: running", flush=True)
    try:
        completed = _run_command(tool.command, project_root)
    except subprocess.TimeoutExpired:
        print(
            f"loadout: cli_tools: {tool.name}: failed (timeout {_CLI_TOOL_TIMEOUT_SECONDS}s)",
            flush=True,
        )
        return
    except OSError as error:
        print(f"loadout: cli_tools: {tool.name}: failed to start: {error}", flush=True)
        return
    _replay_output(completed.stdout, sys.stdout)
    _replay_output(completed.stderr, sys.stderr)
    if completed.returncode == 0:
        print(f"loadout: cli_tools: {tool.name}: ok", flush=True)
        return
    print(f"loadout: cli_tools: {tool.name}: failed (exit {completed.returncode})", flush=True)


def _run_command(command: str, project_root: Path) -> subprocess.CompletedProcess[str]:
    # Popen so a timeout can kill the process group, not only bash.
    with subprocess.Popen(
        [*_SHELL, command],
        cwd=project_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=_CLI_TOOL_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            process.communicate()
            raise
        return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        process.kill()


def _replay_output(text: str, stream: TextIO) -> None:
    if not text:
        return
    print(text, end="" if text.endswith("\n") else "\n", file=stream, flush=True)
