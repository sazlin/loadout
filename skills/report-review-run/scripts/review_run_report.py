#!/usr/bin/env python3
"""Record PR-review harness timings and render the end-of-run GitHub comment."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_RUN_FILE = Path("REVIEW_RUN.json")
BAR_WIDTH = 16
STAGE_KEYS = ("panel", "resolve", "verifiers", "risk", "merge")
STAGE_HEADERS = (
    "Panel Review",
    "Resolve Issues",
    "Verifiers",
    "Risk Classification",
    "Merge",
)
QUEUED_CELL = "⏳|queued"
GANTT_UNSAFE_RE = re.compile(r"[`#:;,{}|\\%]")
ISO_Z_RE = re.compile(r"Z$")

USAGE = "usage: review_run_report.py {begin,end,change,stage,dashboard,render} ..."


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_iso(raw: str) -> datetime:
    """Parse an ISO-8601 timestamp, accepting a trailing Z."""
    text = raw.strip()
    if not text:
        raise ValueError("empty timestamp")
    parsed = datetime.fromisoformat(ISO_Z_RE.sub("+00:00", text))
    return _as_utc(parsed)


def format_iso(value: datetime) -> str:
    """Return a Z-suffixed UTC ISO timestamp."""
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def format_duration(seconds: int) -> str:
    """Format a non-negative second count as `1h 2m 3s` style text."""
    if seconds < 60:
        return f"{seconds}s"
    minutes, rem = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if rem:
        parts.append(f"{rem}s")
    return " ".join(parts) or "0s"


def sanitize_gantt_label(text: str) -> str:
    """Strip characters that break GitHub mermaid gantt task lines."""
    cleaned = GANTT_UNSAFE_RE.sub(" ", text)
    cleaned = " ".join(cleaned.split())
    return cleaned or "step"


def sanitize_markdown_text(text: str) -> str:
    """Collapse whitespace and drop characters that break GitHub markdown tables or fences."""
    cleaned = " ".join(str(text).split())
    return cleaned.replace("|", "/").replace("`", "")


def empty_run() -> dict[str, Any]:
    """Return a blank run log."""
    return {
        "dashboard_url": None,
        "stage": {},
        "steps": [],
        "changes": [],
    }


def load_run(path: Path) -> dict[str, Any]:
    """Load a run log, or a blank one when the file is missing."""
    if not path.is_file():
        return empty_run()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"run file is not an object: {path}")
    payload.setdefault("dashboard_url", None)
    payload.setdefault("stage", {})
    payload.setdefault("steps", [])
    payload.setdefault("changes", [])
    return payload


def save_run(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a run log as pretty JSON."""
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def begin_step(path: Path, *, section: str, label: str, at: datetime | None = None) -> None:
    """Start a timed step, closing any still-open step first."""
    section_text = section.strip()
    label_text = label.strip()
    if not section_text or not label_text:
        raise ValueError("section and label must be non-empty")
    when = _as_utc(at or _now())
    payload = load_run(path)
    _close_open_step(payload, when)
    payload["steps"].append(
        {
            "section": section_text,
            "label": label_text,
            "started_at": format_iso(when),
            "ended_at": None,
        }
    )
    save_run(path, payload)


def end_step(path: Path, *, at: datetime | None = None) -> None:
    """Close the current open step."""
    payload = load_run(path)
    if not _close_open_step(payload, _as_utc(at or _now())):
        raise ValueError("no open step to end")
    save_run(path, payload)


def _close_open_step(payload: dict[str, Any], when: datetime) -> bool:
    steps = payload.get("steps") or []
    if not steps:
        return False
    last = steps[-1]
    if last.get("ended_at"):
        return False
    last["ended_at"] = format_iso(when)
    return True


def add_change(
    path: Path,
    *,
    sha: str,
    task: str,
    summary: str,
    paths: Sequence[str] | None = None,
) -> None:
    """Append one pushed source change."""
    sha_text = sha.strip()
    task_text = task.strip()
    summary_text = summary.strip()
    if not sha_text or not task_text or not summary_text:
        raise ValueError("sha, task, and summary must be non-empty")
    payload = load_run(path)
    payload["changes"].append(
        {
            "sha": sha_text,
            "task": task_text,
            "summary": summary_text,
            "paths": [item.strip() for item in paths or [] if item.strip()],
        }
    )
    save_run(path, payload)


def set_stage(path: Path, cells: Mapping[str, str]) -> None:
    """Set stage-table cells as `icon|status` strings."""
    payload = load_run(path)
    stage = dict(payload.get("stage") or {})
    for key, value in cells.items():
        text = value.strip()
        if key not in STAGE_KEYS or not text:
            continue
        stage[key] = text
    payload["stage"] = stage
    save_run(path, payload)


def set_dashboard(path: Path, url: str) -> None:
    """Record the Cursor Cloud dashboard URL for this harness run."""
    text = url.strip()
    if not text:
        raise ValueError("dashboard url must be non-empty")
    payload = load_run(path)
    payload["dashboard_url"] = text
    save_run(path, payload)


def _parse_optional_iso(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    return parse_iso(raw)


def _step_seconds(step: Mapping[str, Any]) -> int | None:
    ended = step.get("ended_at")
    started = step.get("started_at")
    if not started or not ended:
        return None
    delta = parse_iso(str(ended)) - parse_iso(str(started))
    return max(0, int(delta.total_seconds()))


def _wall_seconds(steps: Sequence[Mapping[str, Any]]) -> int:
    started_at = [str(step["started_at"]) for step in steps if step.get("started_at")]
    ended_at = [str(step["ended_at"]) for step in steps if step.get("ended_at")]
    if not started_at or not ended_at:
        return 0
    delta = parse_iso(max(ended_at)) - parse_iso(min(started_at))
    return max(0, int(delta.total_seconds()))


def _grouped_sections(steps: Sequence[Mapping[str, Any]]) -> list[tuple[str, list[Mapping[str, Any]]]]:
    order: list[str] = []
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for step in steps:
        section = str(step.get("section") or "Other")
        if section not in grouped:
            grouped[section] = []
            order.append(section)
        grouped[section].append(step)
    return [(name, grouped[name]) for name in order]


def _stage_cell(stage: Mapping[str, Any], key: str) -> str:
    raw = str(stage.get(key) or QUEUED_CELL)
    if "|" not in raw:
        return sanitize_markdown_text(raw)
    icon, status = raw.split("|", 1)
    return f"{sanitize_markdown_text(icon)}<br>{sanitize_markdown_text(status)}"


def _stage_table(stage: Mapping[str, Any]) -> str:
    cells = " | ".join(_stage_cell(stage, key) for key in STAGE_KEYS)
    header = " | ".join(STAGE_HEADERS)
    align = "|:-----:|:-------:|:------:|:----:|:-----:|"
    return f"| {header} |\n{align}\n| {cells} |"


def _share_bar(seconds: int, total: int) -> str:
    if total <= 0 or seconds <= 0:
        filled = 0
    else:
        filled = min(BAR_WIDTH, round(seconds / total * BAR_WIDTH))
    return ("█" * filled) + ("░" * (BAR_WIDTH - filled))


def _duration_row(label: str, seconds: int, total: int, *, bold: bool) -> str:
    shown = format_duration(seconds)
    safe = sanitize_markdown_text(label)
    name = f"**{safe}**" if bold else safe
    time_cell = f"**{shown}**" if bold else shown
    percent = 0 if total <= 0 else round(seconds / total * 100)
    bar = _share_bar(seconds, total)
    return f"| {name} | {time_cell} | `{bar}` {percent}% |"


def _duration_table(steps: Sequence[Mapping[str, Any]]) -> str:
    total = _wall_seconds(steps)
    lines = [
        "#### Duration",
        "",
        "| Step | Time | Share |",
        "| --- | ---: | --- |",
    ]
    for section, section_steps in _grouped_sections(steps):
        finished = [step for step in section_steps if _step_seconds(step) is not None]
        section_total = sum(_step_seconds(step) or 0 for step in finished)
        lines.append(_duration_row(section, section_total, total, bold=True))
        for step in section_steps:
            seconds = _step_seconds(step)
            if seconds is None:
                label = sanitize_markdown_text(str(step.get("label") or "step"))
                lines.append(f"| {label} | in progress | |")
                continue
            lines.append(_duration_row(str(step.get("label") or "step"), seconds, total, bold=False))
    lines.append(_duration_row("Total", total, total, bold=True))
    return "\n".join(lines)


def _gantt_block(steps: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "```mermaid",
        "gantt",
        "    title PR review harness",
        "    dateFormat YYYY-MM-DD HH:mm:ss",
        "    axisFormat %H:%M",
        "    todayMarker off",
    ]
    index = 0
    for section, section_steps in _grouped_sections(steps):
        completed = [step for step in section_steps if _step_seconds(step) is not None]
        if not completed:
            continue
        lines.append(f"    section {sanitize_gantt_label(section)}")
        for step in completed:
            seconds = max(1, _step_seconds(step) or 1)
            started = parse_iso(str(step["started_at"])).strftime("%Y-%m-%d %H:%M:%S")
            label = sanitize_gantt_label(str(step.get("label") or "step"))
            lines.append(f"    {label} :s{index}, {started}, {seconds}s")
            index += 1
    lines.append("```")
    return "\n".join(lines)


def _change_line(index: int, change: Mapping[str, Any]) -> str:
    paths = ", ".join(f"`{sanitize_markdown_text(path)}`" for path in change.get("paths") or [])
    files = f" {paths}: " if paths else " "
    sha = sanitize_markdown_text(str(change.get("sha") or ""))
    task = sanitize_markdown_text(str(change.get("task") or ""))
    summary = sanitize_markdown_text(str(change.get("summary") or ""))
    return f"{index}. `{sha}` {task}.{files}{summary}"


def _changes_section(changes: Sequence[Mapping[str, Any]]) -> str:
    lines = ["#### Changes this run pushed", ""]
    if not changes:
        lines.append("None. This run did not push source commits.")
        return "\n".join(lines)
    for index, change in enumerate(changes, start=1):
        lines.append(_change_line(index, change))
    return "\n".join(lines)


def _bullets(payload: Mapping[str, Any], total: int) -> str:
    lines = [f"- Run finished in {format_duration(total)}."]
    url = payload.get("dashboard_url")
    if url:
        lines.append(f"- Cursor Cloud dashboard for this harness: [open]({url}).")
    return "\n".join(lines)


def render_markdown(payload: Mapping[str, Any]) -> str:
    """Return the GitHub PR comment body for a completed (or aborted) run."""
    steps = list(payload.get("steps") or [])
    stage = payload.get("stage") or {}
    changes = list(payload.get("changes") or [])
    total = _wall_seconds(steps)
    parts = [
        "### PR review harness",
        "",
        _stage_table(stage if isinstance(stage, Mapping) else {}),
        "",
        _bullets(payload, total),
        "",
        _gantt_block(steps),
        "",
        _duration_table(steps),
        "",
        _changes_section(changes),
        "",
    ]
    return "\n".join(parts)


def _print_error(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 2


def _cmd_begin(args: argparse.Namespace) -> int:
    try:
        begin_step(
            args.file,
            section=args.section,
            label=args.label,
            at=_parse_optional_iso(args.at),
        )
    except ValueError as error:
        return _print_error(str(error))
    return 0


def _cmd_end(args: argparse.Namespace) -> int:
    try:
        end_step(args.file, at=_parse_optional_iso(args.at))
    except ValueError as error:
        return _print_error(str(error))
    return 0


def _cmd_change(args: argparse.Namespace) -> int:
    try:
        add_change(
            args.file,
            sha=args.sha,
            task=args.task,
            summary=args.summary,
            paths=args.path or [],
        )
    except ValueError as error:
        return _print_error(str(error))
    return 0


def _cmd_stage(args: argparse.Namespace) -> int:
    cells = {
        "panel": args.panel,
        "resolve": args.resolve,
        "verifiers": args.verifiers,
        "risk": args.risk,
        "merge": args.merge,
    }
    set_stage(args.file, {key: value for key, value in cells.items() if value})
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    try:
        set_dashboard(args.file, args.url)
    except ValueError as error:
        return _print_error(str(error))
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    markdown = render_markdown(load_run(args.file))
    if args.out is not None:
        args.out.write_text(markdown, encoding="utf-8")
        return 0
    sys.stdout.write(markdown)
    return 0


def _add_file_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_RUN_FILE,
        help="run log JSON (default: REVIEW_RUN.json)",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="review_run_report.py")
    sub = parser.add_subparsers(dest="cmd")
    begin = sub.add_parser("begin")
    _add_file_option(begin)
    begin.add_argument("--section", required=True)
    begin.add_argument("--label", required=True)
    begin.add_argument("--at")
    begin.set_defaults(func=_cmd_begin)
    end = sub.add_parser("end")
    _add_file_option(end)
    end.add_argument("--at")
    end.set_defaults(func=_cmd_end)
    change = sub.add_parser("change")
    _add_file_option(change)
    change.add_argument("--sha", required=True)
    change.add_argument("--task", required=True)
    change.add_argument("--summary", required=True)
    change.add_argument("--path", action="append", default=[])
    change.set_defaults(func=_cmd_change)
    stage = sub.add_parser("stage")
    _add_file_option(stage)
    for key in STAGE_KEYS:
        stage.add_argument(f"--{key}")
    stage.set_defaults(func=_cmd_stage)
    dashboard = sub.add_parser("dashboard")
    _add_file_option(dashboard)
    dashboard.add_argument("url")
    dashboard.set_defaults(func=_cmd_dashboard)
    render = sub.add_parser("render")
    _add_file_option(render)
    render.add_argument("--out", type=Path)
    render.set_defaults(func=_cmd_render)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run a subcommand. Missing subcommand is usage on stderr, exit 2."""
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not args.cmd:
        print(USAGE, file=sys.stderr)
        return 2
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
