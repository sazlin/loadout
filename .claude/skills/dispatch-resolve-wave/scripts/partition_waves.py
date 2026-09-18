#!/usr/bin/env python3
"""Partition hashed resolve tasks into file-disjoint waves."""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

WAVE_CAP = 4
# Title+Files must appear in this many lines after a sequential TASK heading.
TEMPLATE_LOOKAHEAD = 8

HEADING_RE = re.compile(r"^##\s+(TASK-\d+)\s+\[(open|done|blocked)\]")
TITLE_LINE_RE = re.compile(r"\*\*Title:\*\*\s+\S")
FILES_LINE_RE = re.compile(r"\*\*Files:\*\*\s*(.*)")
BACKTICK_PATH_RE = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class TaskSpec:
    id: str
    status: str
    files: frozenset[str]


def _is_unclear(files: frozenset[str]) -> bool:
    if not files:
        return True
    if "*" in files:
        return True
    return files == frozenset({"."})


def _task_id_for(number: int) -> str:
    return f"TASK-{number:03d}"


def _is_template_heading(lines: list[str], index: int, task_id: str) -> bool:
    heading = HEADING_RE.match(lines[index])
    if heading is None or heading.group(1) != task_id:
        return False
    window = lines[index + 1 : index + 1 + TEMPLATE_LOOKAHEAD]
    has_title = False
    has_files = False
    for line in window:
        stripped = line.strip()
        if TITLE_LINE_RE.match(stripped) is not None:
            has_title = True
        if FILES_LINE_RE.match(stripped) is not None:
            has_files = True
        if has_title and has_files:
            return True
    return False


def parse_tasks(text: str) -> list[TaskSpec]:
    """Parse sequential TASK-00N template headings into TaskSpec rows.

    Only sequential template headings count. An injected TASK-099 body heading
    is skipped unless it is the next id and has Title plus Files in the next
    TEMPLATE_LOOKAHEAD lines. Any TASK-digits heading still ends Files collection
    for the previous task so forged paths do not attach to it.
    """
    tasks: list[TaskSpec] = []
    lines = text.splitlines()
    expected_n = 1
    index = 0
    while index < len(lines):
        expected_id = _task_id_for(expected_n)
        heading = HEADING_RE.match(lines[index])
        if heading is None or not _is_template_heading(lines, index, expected_id):
            index += 1
            continue
        status = heading.group(2)
        index += 1
        files: set[str] = set()
        while index < len(lines) and HEADING_RE.match(lines[index]) is None:
            files_match = FILES_LINE_RE.match(lines[index].strip())
            if files_match is not None:
                files.update(BACKTICK_PATH_RE.findall(files_match.group(1)))
            index += 1
        tasks.append(TaskSpec(id=expected_id, status=status, files=frozenset(files)))
        expected_n += 1
    return tasks


def next_wave(tasks: list[TaskSpec], *, cap: int = WAVE_CAP) -> list[TaskSpec]:
    """Return the next file-disjoint wave of open tasks, up to cap."""
    wave: list[TaskSpec] = []
    used_files: set[str] = set()

    for task in tasks:
        if task.status != "open":
            continue
        if _is_unclear(task.files):
            if wave:
                continue
            return [task]
        if task.files & used_files:
            continue
        wave.append(task)
        used_files.update(task.files)
        if len(wave) >= cap:
            break

    return wave


def main(argv: list[str] | None = None) -> int:
    """Print the next resolve wave as JSON for the given tasks file."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: partition_waves.py <tasks-file>", file=sys.stderr)
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")
    wave = next_wave(parse_tasks(text))
    print(json.dumps({"wave": [task.id for task in wave]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
