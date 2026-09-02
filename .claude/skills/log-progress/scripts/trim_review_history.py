#!/usr/bin/env python3
"""Drop REVIEW_HISTORY.md entries older than 30 days."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

RETENTION_DAYS = 30
MAX_UNPARSEABLE_ENTRIES = 50
DEFAULT_HISTORY = Path("REVIEW_HISTORY.md")
ENTRY_HEADING_RE = re.compile(r"^##\s+(\S+)\s+[\u2014\u2013-]\s+.+$")


def parse_entry_timestamp(raw: str) -> datetime | None:
    """Return a UTC datetime for an ISO heading timestamp, or None if invalid."""
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _keep_entry(timestamp: str, cutoff: datetime) -> bool:
    parsed = parse_entry_timestamp(timestamp)
    if parsed is None:
        return True
    return parsed >= cutoff


def _heading_text(line: str) -> str:
    return line.splitlines()[0] if line else ""


def _split_entries(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = text.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if ENTRY_HEADING_RE.match(_heading_text(line))]
    if not starts:
        return text, []
    preamble = "".join(lines[: starts[0]])
    entries: list[tuple[str, str]] = []
    for index, begin in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        match = ENTRY_HEADING_RE.match(_heading_text(lines[begin]))
        entries.append((match.group(1), "".join(lines[begin:end])))
    return preamble, entries


def _bound_unparseable_entries(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Keep at most MAX_UNPARSEABLE_ENTRIES blocks whose headings lack ISO timestamps."""
    unparseable = [
        index for index, (timestamp, _) in enumerate(entries) if parse_entry_timestamp(timestamp) is None
    ]
    excess = len(unparseable) - MAX_UNPARSEABLE_ENTRIES
    if excess <= 0:
        return entries
    drop = set(unparseable[:excess])
    return [entry for index, entry in enumerate(entries) if index not in drop]


def trim_review_history(text: str, *, now: datetime | None = None) -> str:
    """Return text with entries older than 30 days removed."""
    when = now if now is not None else datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    cutoff = when.astimezone(UTC) - timedelta(days=RETENTION_DAYS)
    preamble, entries = _split_entries(text)
    if not entries:
        return text
    kept = [(timestamp, body) for timestamp, body in entries if _keep_entry(timestamp, cutoff)]
    kept = _bound_unparseable_entries(kept)
    return preamble + "".join(body for _, body in kept)


def _atomic_write_text(path: Path, text: str) -> None:
    """Write text to path atomically via a temp file in the same directory."""
    fd, tmp_path_str = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def trim_review_history_file(path: Path, *, now: datetime | None = None) -> None:
    """Rewrite path in place, or do nothing when the file is missing."""
    if not path.is_file():
        return
    original = path.read_text(encoding="utf-8")
    trimmed = trim_review_history(original, now=now)
    if trimmed != original:
        _atomic_write_text(path, trimmed)


def main(argv: list[str] | None = None) -> int:
    """Trim REVIEW_HISTORY.md in cwd, or the given path."""
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else DEFAULT_HISTORY
    trim_review_history_file(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
