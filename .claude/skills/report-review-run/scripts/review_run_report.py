#!/usr/bin/env python3
"""Record PR-review harness timings and render the end-of-run GitHub comment."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

BAR_WIDTH = 16
STAGES: tuple[tuple[str, str], ...] = (
    ("panel", "Panel Review"),
    ("resolve", "Resolve Issues"),
    ("verifiers", "Verifiers"),
    ("risk", "Risk Classification"),
    ("merge", "Merge"),
)
STAGE_KEYS = tuple(key for key, _ in STAGES)
QUEUED_CELL = "⏳|queued"
GANTT_UNSAFE_RE = re.compile(r"[`#:;,{}|\\%]")
ISO_Z_RE = re.compile(r"Z$")
MAX_STEPS = 64
MAX_CHANGES = 32
MAX_PATHS_PER_CHANGE = 24
MAX_SUMMARY_CHARS = 200
MAX_FIELD_CHARS = 160
MAX_RUN_FILE_BYTES = 1_048_576
RENDER_MAX_BYTES = 60_000
MAX_RENDER_PATHS = 12
GANTT_OMITTED = "_Gantt omitted to stay under GitHub's comment size limit._"
DASHBOARD_HOST = "cursor.com"
DASHBOARD_PATH_PREFIX = "/agents/"
DASHBOARD_UNSAFE = frozenset(" \t\r\n()'\"")

USAGE = "usage: review_run_report.py {reset,begin,end,change,stage,dashboard,render} ..."


class Step(TypedDict):
    section: str
    label: str
    started_at: str
    ended_at: str | None


class Change(TypedDict):
    sha: str
    task: str
    summary: str
    paths: list[str]


class RunLog(TypedDict):
    dashboard_url: str | None
    stage: dict[str, str]
    steps: list[Step]
    changes: list[Change]


def default_run_file() -> Path:
    """Return a per-harness run log path outside the review worktree."""
    raw = os.environ.get("LOADOUT_REVIEW_RUN_ID", "").strip() or str(os.getpid())
    run_id = Path(raw).name
    if not run_id or run_id in {".", ".."}:
        run_id = str(os.getpid())
    return Path(tempfile.gettempdir()) / f"loadout-review-run-{run_id}.json"


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


def empty_run() -> RunLog:
    """Return a blank run log."""
    return {
        "dashboard_url": None,
        "stage": {},
        "steps": [],
        "changes": [],
    }


def _coerce_step(raw: object) -> Step | None:
    if not isinstance(raw, dict):
        return None
    ended = raw.get("ended_at")
    return {
        "section": str(raw.get("section") or "Other"),
        "label": str(raw.get("label") or "step"),
        "started_at": str(raw.get("started_at") or ""),
        "ended_at": None if ended is None else str(ended),
    }


def _coerce_change(raw: object) -> Change | None:
    if not isinstance(raw, dict):
        return None
    paths_raw = raw.get("paths")
    paths = [str(item) for item in paths_raw] if isinstance(paths_raw, list) else []
    return {
        "sha": str(raw.get("sha") or ""),
        "task": str(raw.get("task") or ""),
        "summary": str(raw.get("summary") or ""),
        "paths": paths,
    }


def _coerce_run(payload: object) -> RunLog:
    if not isinstance(payload, dict):
        return empty_run()
    url = payload.get("dashboard_url")
    stage_raw = payload.get("stage")
    stage: dict[str, str] = {}
    if isinstance(stage_raw, dict):
        stage = {str(key): str(value) for key, value in stage_raw.items()}
    steps_raw = payload.get("steps")
    steps: list[Step] = []
    if isinstance(steps_raw, list):
        for item in steps_raw:
            step = _coerce_step(item)
            if step is not None:
                steps.append(step)
    changes_raw = payload.get("changes")
    changes: list[Change] = []
    if isinstance(changes_raw, list):
        for item in changes_raw:
            change = _coerce_change(item)
            if change is not None:
                changes.append(change)
    return {
        "dashboard_url": url if isinstance(url, str) else None,
        "stage": stage,
        "steps": steps,
        "changes": changes,
    }


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]


def _lock_path(path: Path) -> Path:
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:24]
    return Path(tempfile.gettempdir()) / f"loadout-review-run-{digest}.lock"


@contextmanager
def _exclusive_run_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(_lock_path(path), "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_run(path: Path) -> RunLog:
    """Load a run log, or a blank one when the file is missing or unreadable."""
    if not path.is_file():
        return empty_run()
    try:
        raw = path.read_bytes()
    except OSError:
        return empty_run()
    if len(raw) > MAX_RUN_FILE_BYTES:
        return empty_run()
    try:
        payload: object = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
        return empty_run()
    return _coerce_run(payload)


def save_run(path: Path, payload: RunLog) -> None:
    """Write a run log as pretty JSON via a same-directory replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def _update_run(path: Path, mutate: Callable[[RunLog], None]) -> None:
    with _exclusive_run_lock(path):
        payload = load_run(path)
        mutate(payload)
        save_run(path, payload)


def reset_run(path: Path) -> None:
    """Replace any on-disk log with a blank run."""
    with _exclusive_run_lock(path):
        save_run(path, empty_run())


def _cap_tail[T](items: list[T], limit: int) -> None:
    if len(items) > limit:
        del items[:-limit]


def begin_step(path: Path, *, section: str, label: str, at: datetime | None = None) -> None:
    """Start a timed step, closing any still-open step first."""
    section_text = _clip(section.strip(), MAX_FIELD_CHARS)
    label_text = _clip(label.strip(), MAX_FIELD_CHARS)
    if not section_text or not label_text:
        raise ValueError("section and label must be non-empty")

    def mutate(payload: RunLog) -> None:
        when = _as_utc(at or _now())
        _close_open_step(payload, when)
        payload["steps"].append(
            {
                "section": section_text,
                "label": label_text,
                "started_at": format_iso(when),
                "ended_at": None,
            }
        )
        _cap_tail(payload["steps"], MAX_STEPS)

    _update_run(path, mutate)


def end_step(path: Path, *, at: datetime | None = None) -> None:
    """Close the open step that was current when this call started."""
    expected = _open_step_identity(load_run(path))

    def mutate(payload: RunLog) -> None:
        when = _as_utc(at or _now())
        if expected is None or _open_step_identity(payload) != expected:
            raise ValueError("no open step to end")
        _close_open_step(payload, when)

    _update_run(path, mutate)


def _open_step_identity(payload: RunLog) -> tuple[str, str, str] | None:
    steps = payload["steps"]
    if not steps:
        return None
    last = steps[-1]
    if last["ended_at"]:
        return None
    return (last["section"], last["label"], last["started_at"])


def _close_open_step(payload: RunLog, when: datetime) -> bool:
    steps = payload["steps"]
    if not steps:
        return False
    last = steps[-1]
    if last["ended_at"]:
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
    sha_text = _clip(sha.strip(), MAX_FIELD_CHARS)
    task_text = _clip(task.strip(), MAX_FIELD_CHARS)
    summary_text = _clip(summary.strip(), MAX_SUMMARY_CHARS)
    if not sha_text or not task_text or not summary_text:
        raise ValueError("sha, task, and summary must be non-empty")
    kept_paths = [item.strip() for item in paths or [] if item.strip()][:MAX_PATHS_PER_CHANGE]

    def mutate(payload: RunLog) -> None:
        payload["changes"].append(
            {
                "sha": sha_text,
                "task": task_text,
                "summary": summary_text,
                "paths": kept_paths,
            }
        )
        _cap_tail(payload["changes"], MAX_CHANGES)

    _update_run(path, mutate)


def set_stage(path: Path, cells: Mapping[str, str]) -> None:
    """Set stage-table cells as `icon|status` strings."""

    def mutate(payload: RunLog) -> None:
        stage = dict(payload["stage"])
        for key, value in cells.items():
            text = value.strip()
            if key not in STAGE_KEYS or not text:
                continue
            stage[key] = _clip(text, MAX_FIELD_CHARS)
        payload["stage"] = stage

    _update_run(path, mutate)


def allowlisted_dashboard_url(url: object) -> str | None:
    """Return a Cursor Cloud agent URL, or None if it is not allowlisted."""
    if not isinstance(url, str):
        return None
    text = url.strip()
    if not text or any(ch in text for ch in DASHBOARD_UNSAFE):
        return None
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    if parsed.scheme != "https" or host != DASHBOARD_HOST:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    if not path.startswith(DASHBOARD_PATH_PREFIX) or path == DASHBOARD_PATH_PREFIX:
        return None
    return text


def set_dashboard(path: Path, url: str) -> None:
    """Record the Cursor Cloud dashboard URL for this harness run."""
    allowed = allowlisted_dashboard_url(url)
    if allowed is None:
        raise ValueError("dashboard url must be an https://cursor.com/agents/… URL")

    def mutate(payload: RunLog) -> None:
        payload["dashboard_url"] = _clip(allowed, MAX_FIELD_CHARS * 2)

    _update_run(path, mutate)


def _parse_optional_iso(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    return parse_iso(raw)


def _step_seconds(step: Step) -> int | None:
    ended = step["ended_at"]
    started = step["started_at"]
    if not started or not ended:
        return None
    delta = parse_iso(ended) - parse_iso(started)
    return max(0, int(delta.total_seconds()))


def _wall_seconds(steps: Sequence[Step]) -> int:
    started_at = [step["started_at"] for step in steps if step["started_at"]]
    ended_at = [step["ended_at"] for step in steps if step["ended_at"]]
    if not started_at or not ended_at:
        return 0
    delta = parse_iso(max(ended_at)) - parse_iso(min(started_at))
    return max(0, int(delta.total_seconds()))


def _grouped_sections(steps: Sequence[Step]) -> list[tuple[str, list[Step]]]:
    order: list[str] = []
    grouped: dict[str, list[Step]] = {}
    for step in steps:
        section = step["section"] or "Other"
        if section not in grouped:
            grouped[section] = []
            order.append(section)
        grouped[section].append(step)
    return [(name, grouped[name]) for name in order]


def _stage_cell(stage: Mapping[str, str], key: str) -> str:
    raw = str(stage.get(key) or QUEUED_CELL)
    if "|" not in raw:
        return sanitize_markdown_text(raw)
    icon, status = raw.split("|", 1)
    return f"{sanitize_markdown_text(icon)}<br>{sanitize_markdown_text(status)}"


def _stage_table(stage: Mapping[str, str]) -> str:
    cells = " | ".join(_stage_cell(stage, key) for key, _ in STAGES)
    header = " | ".join(title for _, title in STAGES)
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


def _duration_table(steps: Sequence[Step]) -> str:
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
                label = sanitize_markdown_text(step["label"] or "step")
                lines.append(f"| {label} | in progress | |")
                continue
            lines.append(_duration_row(step["label"] or "step", seconds, total, bold=False))
    lines.append(_duration_row("Total", total, total, bold=True))
    return "\n".join(lines)


def _gantt_block(steps: Sequence[Step]) -> str:
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
            started = parse_iso(step["started_at"]).strftime("%Y-%m-%d %H:%M:%S")
            label = sanitize_gantt_label(step["label"] or "step")
            lines.append(f"    {label} :s{index}, {started}, {seconds}s")
            index += 1
    lines.append("```")
    return "\n".join(lines)


def _change_line(index: int, change: Change) -> str:
    raw_paths = list(change["paths"])
    extra_paths = max(0, len(raw_paths) - MAX_RENDER_PATHS)
    shown_paths = raw_paths[:MAX_RENDER_PATHS]
    paths = ", ".join(f"`{sanitize_markdown_text(path)}`" for path in shown_paths)
    if extra_paths:
        paths = f"{paths}, {extra_paths} more paths omitted" if paths else f"{extra_paths} more paths omitted"
    files = f" {paths}: " if paths else " "
    sha = sanitize_markdown_text(change["sha"])
    task = sanitize_markdown_text(change["task"])
    summary = sanitize_markdown_text(change["summary"])
    return f"{index}. `{sha}` {task}.{files}{summary}"


def _changes_section(changes: Sequence[Change], omitted: int = 0) -> str:
    lines = ["#### Changes this run pushed", ""]
    if not changes and omitted == 0:
        lines.append("None. This run did not push source commits.")
        return "\n".join(lines)
    for index, change in enumerate(changes, start=1):
        lines.append(_change_line(index, change))
    if omitted:
        lines.append(f"_… {omitted} more changes omitted._")
    return "\n".join(lines)


def _bullets(payload: RunLog, total: int) -> str:
    lines = [f"- Run finished in {format_duration(total)}."]
    url = allowlisted_dashboard_url(payload["dashboard_url"])
    if url:
        lines.append(f"- Cursor Cloud dashboard for this harness: [open]({url}).")
    return "\n".join(lines)


def _compose_markdown(
    payload: RunLog,
    *,
    include_gantt: bool,
    changes: Sequence[Change],
    omitted_changes: int,
) -> str:
    steps = list(payload["steps"])
    stage = payload["stage"]
    total = _wall_seconds(steps)
    gantt = _gantt_block(steps) if include_gantt else GANTT_OMITTED
    parts = [
        "### PR review harness",
        "",
        _stage_table(stage),
        "",
        _bullets(payload, total),
        "",
        gantt,
        "",
        _duration_table(steps),
        "",
        _changes_section(changes, omitted_changes),
        "",
    ]
    return "\n".join(parts)


def render_markdown(payload: RunLog) -> str:
    """Return the GitHub PR comment body for a completed (or aborted) run."""
    payload = _coerce_run(payload)
    changes = list(payload["changes"])
    include_gantt = True
    shown = changes
    omitted = 0
    while True:
        body = _compose_markdown(
            payload,
            include_gantt=include_gantt,
            changes=shown,
            omitted_changes=omitted,
        )
        if len(body.encode("utf-8")) <= RENDER_MAX_BYTES:
            return body
        if include_gantt:
            include_gantt = False
            continue
        if shown:
            omitted += 1
            shown = shown[:-1]
            continue
        encoded = body.encode("utf-8")[: RENDER_MAX_BYTES - 24]
        trimmed = encoded.decode("utf-8", errors="ignore").rstrip()
        return f"{trimmed}\n\n_… truncated._\n"


def _print_error(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 2


def _run_file(args: argparse.Namespace) -> Path:
    if args.file is not None:
        return args.file
    return default_run_file()


def _cmd_reset(args: argparse.Namespace) -> int:
    try:
        reset_run(_run_file(args))
    except (ValueError, OSError) as error:
        return _print_error(str(error))
    return 0


def _cmd_begin(args: argparse.Namespace) -> int:
    try:
        begin_step(
            _run_file(args),
            section=args.section,
            label=args.label,
            at=_parse_optional_iso(args.at),
        )
    except (ValueError, json.JSONDecodeError, TypeError, OSError) as error:
        return _print_error(str(error))
    return 0


def _cmd_end(args: argparse.Namespace) -> int:
    try:
        end_step(_run_file(args), at=_parse_optional_iso(args.at))
    except (ValueError, json.JSONDecodeError, TypeError, OSError) as error:
        return _print_error(str(error))
    return 0


def _cmd_change(args: argparse.Namespace) -> int:
    try:
        add_change(
            _run_file(args),
            sha=args.sha,
            task=args.task,
            summary=args.summary,
            paths=args.path or [],
        )
    except (ValueError, json.JSONDecodeError, TypeError, OSError) as error:
        return _print_error(str(error))
    return 0


def _cmd_stage(args: argparse.Namespace) -> int:
    cells = {key: getattr(args, key) for key, _ in STAGES}
    try:
        set_stage(_run_file(args), {key: value for key, value in cells.items() if value})
    except (ValueError, json.JSONDecodeError, TypeError, OSError) as error:
        return _print_error(str(error))
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    try:
        set_dashboard(_run_file(args), args.url)
    except (ValueError, json.JSONDecodeError, TypeError, OSError) as error:
        return _print_error(str(error))
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    path = _run_file(args)
    try:
        with _exclusive_run_lock(path):
            markdown = render_markdown(load_run(path))
    except (ValueError, json.JSONDecodeError, TypeError, OSError) as error:
        return _print_error(str(error))
    if args.out is not None:
        args.out.write_text(markdown, encoding="utf-8")
        return 0
    sys.stdout.write(markdown)
    return 0


def _add_file_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="run log JSON (default: $TMPDIR/loadout-review-run-<id>.json, not the worktree)",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="review_run_report.py")
    sub = parser.add_subparsers(dest="cmd")
    reset = sub.add_parser("reset")
    _add_file_option(reset)
    reset.set_defaults(func=_cmd_reset)
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
    for key, _ in STAGES:
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
