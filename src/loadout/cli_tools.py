"""Run loadout-declared CLI install commands. Failures are reported, never fatal."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TextIO

from loadout.models import CliTool

_SHELL = ("bash", "-c")


def run_cli_tools(tools: list[CliTool], project_root: Path) -> None:
    """Run each command in ``project_root``. Continue after failures."""
    for tool in tools:
        _run_one(tool, project_root)


def _run_one(tool: CliTool, project_root: Path) -> None:
    print(f"loadout: cli_tools: {tool.name}: running")
    try:
        completed = subprocess.run(
            [*_SHELL, tool.command],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        print(f"loadout: cli_tools: {tool.name}: failed to start: {error}")
        return
    _replay_output(completed.stdout, sys.stdout)
    _replay_output(completed.stderr, sys.stderr)
    if completed.returncode == 0:
        print(f"loadout: cli_tools: {tool.name}: ok")
        return
    print(f"loadout: cli_tools: {tool.name}: failed (exit {completed.returncode})")


def _replay_output(text: str, stream: TextIO) -> None:
    if not text:
        return
    print(text, end="" if text.endswith("\n") else "\n", file=stream)
