#!/usr/bin/env python3
"""Fail-open skill-load telemetry hook. Stdlib only; python3 >= 3.9."""

from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HOOK_VERSION = "1.0.0"
SCOPE_CURSOR = "cursor.skill-telemetry"
SCOPE_CLAUDE = "claude.skill-telemetry"
SDK_NAME = "skill-telemetry-hook"
READS = "skill.reads"
TURNS = "skill.turns"
DISCOVERED = "skill.discovered_on_session_start"
UNIT_READ = "{read}"
UNIT_TURN = "{turn}"
UNIT_SKILL = "{skill}"
DESC_READS = "Hydrations of a skill body, by skill name and invocation kind"
DESC_TURNS = "Turns in which at least one skill was offered to the model"
DESC_DISCOVERED = "Skills discovered when the session started"
STATE_VERSION = 1
LOCK_WAIT_S = 1.0
LOCK_RETRY_S = 0.05
GC_INTERVAL_S = 3600.0
TTL_S = 7 * 24 * 3600
SCAN_BUDGET_S = 0.3
SCAN_MAX_DEPTH = 6
SKILL_HEAD_BYTES = 4096
DEFAULT_TIMEOUT_MS = 2000
SKIP_DIRS = frozenset({".git", "node_modules", "vendor", "dist", "build", "target", ".venv", "venv", "__pycache__"})
KEEP_DOT_DIRS = frozenset({".cursor", ".agents", ".claude", ".codex"})
WORKSPACE_PARENTS = frozenset({".cursor", ".agents"})
PROMPT_TOKEN = re.compile(r"(^|\s)/([A-Za-z0-9][\w-]*)(?=\s|$)")
DISABLED_MODEL = re.compile(r"(?m)^disable-model-invocation:\s*true\s*$")
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
SESSION_ID_MAX_LEN = 128
STDIN_MAX_BYTES = 1_048_576
STDIN_CHUNK = 65_536
STDIN_EVENT_PEEK = 8192
HOOK_EVENT_RE = re.compile(rb'"(?:hook_event_name|hookEventName)"\s*:\s*"([^"\\]{1,80})"')
STATE_DIR_MODE = 0o700
STATE_FILE_MODE = 0o600
GC_SKIP_NAMES = frozenset({"gc", "gc.lock", "debug.log"})
GC_UNLINK_SUFFIXES = frozenset({".json", ".lock", ".exporting", ".dirty"})
GC_MAX_UNLINKS = 256
EXPORT_CLAIM_GRACE_S = 1.0
BOOL_ATTRS = frozenset({"agent.is_subagent"})

AttrValue = str | bool
Attrs = dict[str, AttrValue]


@dataclass
class Emission:
    instrument: str
    value: int
    attributes: Attrs


@dataclass
class State:
    version: int = STATE_VERSION
    harness: str = "cursor"
    conversation_id: str = ""
    started_at_unix_nano: int = 0
    model: str = "unknown"
    repo: str = "none"
    is_subagent: bool = False
    parent_conversation_id: str | None = None
    offered: bool = False
    discovered_count: int = 0
    discovered_emitted: bool = False
    providers: dict[str, str] = field(default_factory=dict)
    user_this_turn: list[str] = field(default_factory=list)
    stops_seen: int = 0
    series: dict[str, int] = field(default_factory=dict)


def decide(state: State, event: dict[str, Any], attrs: Attrs) -> list[Emission]:
    """Pure plugin-equivalent counter logic. Mutates ``state``."""
    kind = event.get("type")
    if kind == "session_start":
        return _decide_session_start(state, event, attrs)
    if kind == "turn_start":
        state.user_this_turn.clear()
        return []
    if kind == "turn_end":
        return [Emission(TURNS, 1, dict(attrs))] if state.offered else []
    if kind == "user_skill":
        return _decide_user_skill(state, event, attrs)
    if kind == "model_read":
        return _decide_model_read(state, event, attrs)
    return []


def classify_skill_path(file_path: str, roots: list[tuple[Path, str]]) -> tuple[str, str] | None:
    """Return ``(name, provider)`` for a skill body path, else None."""
    path = Path(file_path)
    if path.name != "SKILL.md":
        return None
    resolved = _resolve(path)
    matches: list[tuple[int, str, str]] = []
    for root, provider in roots:
        rel = _relative_to(resolved, _resolve(root))
        if rel is None:
            continue
        parts = rel.parts
        if len(parts) == 2 and parts[1] == "SKILL.md":
            matches.append((len(str(_resolve(root))), parts[0].lower(), provider))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1], matches[0][2]


def parse_prompt_skill_names(prompt: str, known: set[str]) -> list[str]:
    """Return known ``/name`` invocations in ``prompt``. Bang-commands are ignored."""
    if not prompt:
        return []
    trimmed = prompt.lstrip()
    if trimmed.startswith("!"):
        return []
    found: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        key = name.lower()
        if key in known and key not in seen:
            seen.add(key)
            found.append(key)

    if trimmed.startswith("/"):
        token = trimmed[1:].split(None, 1)[0] if trimmed[1:] else ""
        if token and "/" not in token:
            add(token)
    for match in PROMPT_TOKEN.finditer(prompt):
        add(match.group(2))
    return found


def encode_snapshot(state: State, *, now_ns: int, service_name: str, harness: str) -> bytes:
    """Hand-encode an OTLP ExportMetricsServiceRequest protobuf."""
    grouped: dict[str, list[tuple[Attrs, int]]] = {}
    for key, value in state.series.items():
        instrument, attrs = _parse_series_key(key)
        grouped.setdefault(instrument, []).append((attrs, value))
    metrics = []
    for instrument, unit, description, monotonic in (
        (READS, UNIT_READ, DESC_READS, True),
        (TURNS, UNIT_TURN, DESC_TURNS, True),
        (DISCOVERED, UNIT_SKILL, DESC_DISCOVERED, False),
    ):
        rows = grouped.get(instrument)
        if not rows:
            continue
        points = [_number_point(attrs, state.started_at_unix_nano, now_ns, value) for attrs, value in rows]
        metrics.append(_metric(instrument, description, unit, points, monotonic))
    scope_name = SCOPE_CURSOR if harness == "cursor" else SCOPE_CLAUDE
    scope = _string_field(1, scope_name) + _string_field(2, HOOK_VERSION)
    scope_metrics = _len_field(1, scope) + b"".join(_len_field(2, item) for item in metrics)
    resource = _resource(
        [
            ("service.name", service_name),
            ("telemetry.sdk.name", SDK_NAME),
            ("telemetry.sdk.language", "python"),
            ("telemetry.sdk.version", HOOK_VERSION),
        ]
    )
    resource_metrics = _len_field(1, resource) + _len_field(2, scope_metrics)
    return _len_field(1, resource_metrics)


def main(argv: list[str] | None = None, stdin: bytes | None = None) -> int:
    """Hook entry. Always exits 0; never raises to the caller."""
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        return _run(args, stdin)
    except Exception as exc:  # noqa: BLE001 - fail-open: never raise into the agent
        _debug(f"error: {exc}")
        _emit_allow(_mode_from_args(args), None)
        return 0


def _run(args: list[str], stdin: bytes | None) -> int:
    if args and args[0] == "--export":
        blob = args[1] if len(args) > 1 else ""
        claim = args[2] if len(args) > 2 else ""
        _export_file(blob, claim)
        return 0
    mode = _mode_from_args(args)
    raw, over_cap = _capped_stdin(stdin)
    if over_cap:
        _emit_allow(mode, _event_name_from_prefix(raw))
        return 0
    payload = _parse_payload(raw)
    event_name = _event_name(payload)
    if payload is None:
        _emit_allow(mode, event_name)
        return 0
    if not _export_enabled():
        _emit_allow(mode, event_name)
        return 0
    _handle_event(mode, payload)
    _emit_allow(mode, event_name)
    return 0


def _mode_from_args(args: list[str] | None) -> str:
    if args and args[0] and args[0] != "--export":
        return args[0]
    return "claude"


def _capped_stdin(stdin: bytes | None) -> tuple[bytes, bool]:
    """Read hook stdin, capped at STDIN_MAX_BYTES. over_cap skips parse."""
    if stdin is not None:
        if len(stdin) > STDIN_MAX_BYTES:
            return stdin[:STDIN_EVENT_PEEK], True
        return stdin, False
    head = sys.stdin.buffer.read(STDIN_MAX_BYTES + 1)
    if len(head) <= STDIN_MAX_BYTES:
        return head, False
    while sys.stdin.buffer.read(STDIN_CHUNK):
        pass
    return head[:STDIN_EVENT_PEEK], True


def _event_name_from_prefix(raw: bytes) -> str | None:
    match = HOOK_EVENT_RE.search(raw[:STDIN_EVENT_PEEK])
    if match:
        return match.group(1).decode("ascii")
    return os.environ.get("HOOK_EVENT") or None


def _parse_payload(raw: bytes) -> dict[str, Any] | None:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None
    text = text.removeprefix("\ufeff")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _event_name(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return os.environ.get("HOOK_EVENT") or None
    name = payload.get("hook_event_name") or payload.get("hookEventName")
    return name if isinstance(name, str) and name else os.environ.get("HOOK_EVENT") or None


def _export_enabled() -> bool:
    if not _flag(os.environ.get("SKILL_TELEMETRY_ENABLED"), True):
        return False
    if not (os.environ.get("OTEL_SERVICE_NAME") or "").strip():
        return False
    if not _metrics_url():
        return False
    protocol = (os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL") or "http/protobuf").strip()
    if not protocol:
        protocol = "http/protobuf"
    return protocol == "http/protobuf"


def _flag(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _emit_allow(mode: str, event_name: str | None) -> None:
    sys.stdout.write(_allow_payload(mode, event_name) + "\n")
    sys.stdout.flush()


def _allow_payload(mode: str, event_name: str | None) -> str:
    if mode != "cursor":
        return "{}"
    if event_name == "beforeReadFile":
        return '{"permission":"allow"}'
    if event_name == "beforeSubmitPrompt":
        return '{"continue":true}'
    return "{}"


def _handle_event(mode: str, payload: dict[str, Any]) -> None:
    session_id = _session_id(mode, payload)
    if not session_id:
        return
    state_dir = _state_dir()
    if state_dir is None:
        return
    event_name = _event_name(payload) or ""
    if _is_non_skill_file_read(event_name, payload):
        return
    if event_name in {"sessionStart", "SessionStart"}:
        _maybe_gc(state_dir, time.time(), force=True)
    elif event_name not in {"beforeReadFile", "PreToolUse"}:
        _maybe_gc(state_dir, time.time(), force=False)
    lock_path = _state_child(state_dir, session_id, ".lock")
    if lock_path is None:
        return
    result = _with_lock(lock_path, lambda: _apply_locked(mode, payload, session_id, state_dir))
    if result is None:
        return
    state, changed = result
    if not changed and event_name not in {"sessionEnd", "SessionEnd"}:
        return
    if not state.series:
        return
    _export_state(state, mode, state_dir)


def _is_non_skill_file_read(event_name: str, payload: dict[str, Any]) -> bool:
    if event_name == "beforeReadFile":
        path = payload.get("file_path")
    elif event_name == "PreToolUse":
        tool = payload.get("tool_name") or payload.get("toolName") or ""
        if tool != "Read":
            return False
        tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
        if not isinstance(tool_input, dict):
            return True
        path = tool_input.get("file_path") or tool_input.get("path")
    else:
        return False
    return not isinstance(path, str) or Path(path).name != "SKILL.md"


def _apply_locked(mode: str, payload: dict[str, Any], session_id: str, state_dir: Path) -> tuple[State, bool]:
    event_name = _event_name(payload) or ""
    path = _state_child(state_dir, session_id, ".json")
    if path is None:
        return State(conversation_id=session_id, harness=mode), False
    if event_name == "subagentStart":
        _record_subagent(state_dir, payload, session_id)
        existing = _load_state(path)
        return existing or State(conversation_id=session_id, harness=mode), False
    deadline = time.monotonic() + SCAN_BUDGET_S
    roots = _ordered_roots(_workspace_roots(payload), deadline)
    if event_name in {"sessionStart", "SessionStart"}:
        state = _load_state(path)
        if state is None:
            state = _new_root_state(mode, payload, session_id, state_dir)
        else:
            _refresh_model(state, payload)
            workspaces = _workspace_roots(payload)
            if workspaces:
                state.repo = repo_name(workspaces[0])
    else:
        state = _load_state(path)
        if state is None:
            state = _lazy_state(mode, payload, session_id, state_dir, roots, deadline)
        else:
            _refresh_model(state, payload)
    before = dict(state.series)
    _dispatch(mode, state, payload, roots, deadline)
    serialized = json.dumps(_state_to_dict(state), separators=(",", ":"))
    try:
        unchanged = path.is_file() and path.read_text() == serialized
    except OSError:
        unchanged = False
    if not unchanged:
        _atomic_write(path, serialized)
    changed = state.series != before or event_name in {"sessionEnd", "SessionEnd"}
    return state, changed


def _dispatch(mode: str, state: State, payload: dict[str, Any], roots: list[tuple[Path, str]], deadline: float) -> None:
    event_name = _event_name(payload) or ""
    attrs = _ctx_attrs(state)
    if mode == "cursor":
        _dispatch_cursor(state, payload, event_name, roots, attrs, deadline)
        return
    _dispatch_claude(state, payload, event_name, roots, attrs, deadline)


def _dispatch_cursor(
    state: State,
    payload: dict[str, Any],
    event_name: str,
    roots: list[tuple[Path, str]],
    attrs: Attrs,
    deadline: float,
) -> None:
    if event_name == "sessionStart":
        _apply_session_start(state, payload, roots, attrs, deadline, emit=True)
        return
    if event_name == "beforeReadFile":
        _apply_model_read(state, payload.get("file_path"), roots, attrs)
        return
    if event_name == "beforeSubmitPrompt":
        _apply_prompt(state, payload, roots, attrs)
        return
    if event_name == "stop":
        _apply_emissions(state, decide(state, {"type": "turn_end"}, attrs))
        state.stops_seen += 1
        state.user_this_turn.clear()
        return
    if event_name == "sessionEnd":
        if state.offered and state.stops_seen == 0:
            _apply_emissions(state, decide(state, {"type": "turn_end"}, attrs))
            state.stops_seen += 1
        return


def _dispatch_claude(
    state: State,
    payload: dict[str, Any],
    event_name: str,
    roots: list[tuple[Path, str]],
    attrs: Attrs,
    deadline: float,
) -> None:
    if event_name == "SessionStart":
        source = payload.get("source")
        emit = source == "startup" or source is None
        _apply_session_start(state, payload, roots, attrs, deadline, emit=emit)
        return
    if event_name == "UserPromptSubmit":
        _apply_prompt(state, payload, roots, attrs)
        return
    if event_name == "PreToolUse":
        _apply_claude_tool(state, payload, roots, attrs)
        return
    if event_name == "Stop":
        _apply_emissions(state, decide(state, {"type": "turn_end"}, attrs))
        state.user_this_turn.clear()


def _apply_session_start(
    state: State,
    payload: dict[str, Any],
    roots: list[tuple[Path, str]],
    attrs: Attrs,
    deadline: float,
    *,
    emit: bool,
) -> None:
    del payload
    providers, count, offered = _scan_skills(roots, deadline)
    event = {
        "type": "session_start",
        "skillCount": count,
        "offered": offered,
        "providers": providers,
        "subagent": state.is_subagent,
        "emit": emit,
    }
    _apply_emissions(state, decide(state, event, attrs))


def _apply_model_read(state: State, file_path: Any, roots: list[tuple[Path, str]], attrs: Attrs) -> None:
    if not isinstance(file_path, str) or not file_path:
        return
    classified = classify_skill_path(file_path, roots)
    if classified is None:
        return
    name, provider = classified
    event = {"type": "model_read", "name": name, "provider": provider, "asset": False, "error": False}
    _apply_emissions(state, decide(state, event, attrs))


def _apply_prompt(state: State, payload: dict[str, Any], roots: list[tuple[Path, str]], attrs: Attrs) -> None:
    _apply_emissions(state, decide(state, {"type": "turn_start"}, attrs))
    prompt = payload.get("prompt")
    names = parse_prompt_skill_names(prompt if isinstance(prompt, str) else "", set(state.providers))
    for name in names:
        _apply_emissions(state, decide(state, {"type": "user_skill", "name": name}, attrs))
    for name, provider in _attachment_skills(payload.get("attachments"), roots):
        if name not in state.providers:
            state.providers[name] = provider
        _apply_emissions(state, decide(state, {"type": "user_skill", "name": name}, attrs))


def _apply_claude_tool(state: State, payload: dict[str, Any], roots: list[tuple[Path, str]], attrs: Attrs) -> None:
    tool_name = payload.get("tool_name") or payload.get("toolName") or ""
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    if tool_name == "Skill":
        raw = tool_input.get("skill")
        if not isinstance(raw, str) or not raw:
            return
        name = raw.split(":")[-1].lower()
        _apply_emissions(
            state, decide(state, {"type": "model_read", "name": name, "asset": False, "error": False}, attrs)
        )
        return
    if tool_name == "Read":
        path = tool_input.get("file_path") or tool_input.get("path")
        _apply_model_read(state, path, roots, attrs)


def _decide_session_start(state: State, event: dict[str, Any], attrs: Attrs) -> list[Emission]:
    state.offered = bool(event.get("offered"))
    state.providers = dict(event.get("providers") or {})
    state.user_this_turn.clear()
    state.discovered_count = int(event.get("skillCount") or 0)
    emit = event.get("emit", True)
    if state.discovered_count > 0 and not event.get("subagent") and emit and not state.discovered_emitted:
        state.discovered_emitted = True
        return [Emission(DISCOVERED, state.discovered_count, dict(attrs))]
    state.discovered_emitted = True
    return []


def _decide_user_skill(state: State, event: dict[str, Any], attrs: Attrs) -> list[Emission]:
    name = str(event.get("name") or "").lower()
    if not name or name not in state.providers or name in state.user_this_turn:
        return []
    state.user_this_turn.append(name)
    provider = state.providers.get(name, "unknown")
    return [Emission(READS, 1, _read_attrs(attrs, name, "user", provider))]


def _decide_model_read(state: State, event: dict[str, Any], attrs: Attrs) -> list[Emission]:
    if event.get("asset") or event.get("error"):
        return []
    name = str(event.get("name") or "").lower()
    if not name or name in state.user_this_turn:
        return []
    provider = str(event.get("provider") or state.providers.get(name) or "unknown")
    return [Emission(READS, 1, _read_attrs(attrs, name, "model", provider))]


def _read_attrs(attrs: Attrs, name: str, kind: str, provider: str) -> Attrs:
    merged = dict(attrs)
    merged["skill.name"] = name
    merged["skill.invocation_kind"] = kind
    merged["skill.provider"] = provider
    return merged


def _apply_emissions(state: State, rows: list[Emission]) -> None:
    for row in rows:
        key = _series_key(row.instrument, row.attributes)
        state.series[key] = state.series.get(key, 0) + row.value


def _ctx_attrs(state: State) -> Attrs:
    return {
        "agent.is_subagent": bool(state.is_subagent),
        "agent.session.id": state.conversation_id,
        "gen_ai.request.model": state.model or "unknown",
        "vcs.repository.name": state.repo or "none",
    }


def _series_key(instrument: str, attrs: Attrs) -> str:
    parts = [instrument]
    for key in sorted(attrs):
        value = attrs[key]
        rendered = "true" if value is True else "false" if value is False else str(value)
        parts.append(f"{key}={rendered}")
    return "|".join(parts)


def _parse_series_key(key: str) -> tuple[str, Attrs]:
    instrument, *pairs = key.split("|")
    attrs: Attrs = {}
    for pair in pairs:
        name, _, value = pair.partition("=")
        if name in BOOL_ATTRS:
            attrs[name] = value == "true"
        else:
            attrs[name] = value
    return instrument, attrs


def _blank_state(mode: str, payload: dict[str, Any], session_id: str) -> State:
    return State(
        harness=mode,
        conversation_id=session_id,
        started_at_unix_nano=_now_ns(),
        model=_model_from_payload(payload, "unknown"),
        repo=repo_name(_workspace_roots(payload)[0]) if _workspace_roots(payload) else "none",
    )


def _new_root_state(mode: str, payload: dict[str, Any], session_id: str, state_dir: Path) -> State:
    index = _load_subagents(state_dir)
    child = index.get(session_id)
    parent = child.get("parent") if isinstance(child, dict) else None
    parent_id = parent if isinstance(parent, str) and _valid_id(parent) else None
    state = _blank_state(mode, payload, session_id)
    state.is_subagent = bool(child)
    state.parent_conversation_id = parent_id
    return state


def _lazy_state(
    mode: str,
    payload: dict[str, Any],
    session_id: str,
    state_dir: Path,
    roots: list[tuple[Path, str]],
    deadline: float,
) -> State:
    index = _load_subagents(state_dir)
    child = index.get(session_id)
    state = _blank_state(mode, payload, session_id)
    if child:
        return _state_for_known_subagent(state, child, state_dir, roots, deadline=deadline)
    return _state_for_unseen_root(state, roots, session_id, deadline=deadline)


def _state_for_known_subagent(
    state: State,
    child: Any,
    state_dir: Path,
    roots: list[tuple[Path, str]],
    *,
    deadline: float,
) -> State:
    state.is_subagent = True
    parent_id = child.get("parent") if isinstance(child, dict) else None
    state.parent_conversation_id = parent_id if isinstance(parent_id, str) and _valid_id(parent_id) else None
    parent_path = (
        _state_child(state_dir, state.parent_conversation_id, ".json") if state.parent_conversation_id else None
    )
    parent = _load_state(parent_path) if parent_path else None
    if parent is not None:
        state.offered = parent.offered
        state.providers = dict(parent.providers)
        state.discovered_count = parent.discovered_count
    else:
        providers, count, offered = _scan_skills(roots, deadline)
        state.providers = providers
        state.discovered_count = count
        state.offered = offered
    state.discovered_emitted = True
    return state


def _state_for_unseen_root(
    state: State,
    roots: list[tuple[Path, str]],
    session_id: str,
    *,
    deadline: float,
) -> State:
    providers, count, offered = _scan_skills(roots, deadline)
    state.providers = providers
    state.discovered_count = count
    state.offered = offered
    if _is_cloud_session(session_id) and count > 0:
        _apply_emissions(state, [Emission(DISCOVERED, count, _ctx_attrs(state))])
    state.discovered_emitted = True
    return state


def _is_cloud_session(session_id: str) -> bool:
    if os.environ.get("SKILL_TELEMETRY_ASSUME_ROOT") == "1":
        return True
    return session_id.startswith("bc-")


def _session_id(mode: str, payload: dict[str, Any]) -> str:
    if mode == "cursor":
        value = payload.get("conversation_id") or payload.get("session_id") or ""
    else:
        value = payload.get("session_id") or payload.get("conversation_id") or ""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return value if _valid_id(value) else ""


def _valid_id(value: str) -> bool:
    if not value or len(value) > SESSION_ID_MAX_LEN:
        return False
    if "\0" in value or ".." in value or "/" in value or "\\" in value:
        return False
    return SESSION_ID_RE.fullmatch(value) is not None


def _state_child(state_dir: Path, stem: str, suffix: str) -> Path | None:
    if not _valid_id(stem):
        return None
    root = _resolve(state_dir)
    path = _resolve(state_dir / f"{stem}{suffix}")
    rel = _relative_to(path, root)
    if rel is None or len(rel.parts) != 1:
        return None
    return path


def _model_from_payload(payload: dict[str, Any], fallback: str) -> str:
    for key in ("model_id", "model"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _refresh_model(state: State, payload: dict[str, Any]) -> None:
    model = _model_from_payload(payload, "")
    if model:
        state.model = model


def _workspace_roots(payload: dict[str, Any]) -> list[Path]:
    roots: list[Path] = []
    raw = payload.get("workspace_roots")
    if isinstance(raw, list):
        roots.extend(Path(item) for item in raw if isinstance(item, str) and item)
    for env_name in ("CURSOR_PROJECT_DIR", "CLAUDE_PROJECT_DIR"):
        value = os.environ.get(env_name)
        if value:
            roots.append(Path(value))
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd:
        roots.append(Path(cwd))
    if not roots:
        roots.append(Path.cwd())
    seen: set[str] = set()
    unique: list[Path] = []
    for path in roots:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def repo_name(start: Path) -> str:
    """Git origin basename, else directory name, else ``none``."""
    current = _resolve(start)
    while True:
        git = current / ".git"
        if git.exists():
            url = _origin_url(git)
            if url:
                return _last_segment(url)
            return current.name or "none"
        parent = current.parent
        if parent == current:
            return "none"
        current = parent


def _origin_url(git: Path) -> str | None:
    config = git / "config" if git.is_dir() else _gitdir_config(git)
    if config is None or not config.is_file():
        return None
    try:
        text = config.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    in_origin = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_origin = stripped.lower() == '[remote "origin"]'
            continue
        if in_origin and stripped.lower().startswith("url"):
            _, _, value = stripped.partition("=")
            return value.strip() or None
    return None


def _gitdir_config(git_file: Path) -> Path | None:
    try:
        text = git_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        if line.lower().startswith("gitdir:"):
            gitdir = Path(line.split(":", 1)[1].strip())
            if not gitdir.is_absolute():
                gitdir = git_file.parent / gitdir
            return gitdir / "config"
    return None


def _last_segment(url: str) -> str:
    trimmed = url.strip().rstrip("/")
    trimmed = trimmed.removesuffix(".git")
    slash = trimmed.replace("\\", "/").rsplit("/", 1)[-1]
    return slash.rsplit(":", 1)[-1] or "none"


def _ordered_roots(workspaces: list[Path], deadline: float | None = None) -> list[tuple[Path, str]]:
    if deadline is None:
        deadline = time.monotonic() + SCAN_BUDGET_S
    ordered: list[tuple[Path, str]] = []
    seen: set[str] = set()

    def add(path: Path, provider: str) -> None:
        if not path.is_dir():
            return
        key = str(_resolve(path))
        if key in seen:
            return
        seen.add(key)
        ordered.append((path, provider))

    for workspace in workspaces:
        for path in _walk_workspace_skill_roots(workspace, deadline):
            add(path, "workspace")
    home = Path.home()
    add(home / ".cursor" / "skills", "user")
    add(home / ".agents" / "skills", "user")
    for path in _plugin_skill_dirs(deadline):
        add(path, "plugin")
    for workspace in workspaces:
        add(workspace / ".claude" / "skills", "claude")
    add(home / ".claude" / "skills", "claude")
    for workspace in workspaces:
        add(workspace / ".codex" / "skills", "codex")
    add(home / ".codex" / "skills", "codex")
    return ordered


def _walk_workspace_skill_roots(workspace: Path, deadline: float) -> list[Path]:
    found: list[Path] = []
    for rel in (".cursor/skills", ".agents/skills"):
        path = workspace / rel
        if path.is_dir():
            found.append(path)
    stack = [(workspace, 0)]
    while stack and time.monotonic() < deadline:
        current, depth = stack.pop()
        if depth > SCAN_MAX_DEPTH:
            continue
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if time.monotonic() >= deadline:
                break
            if not entry.is_dir():
                continue
            name = entry.name
            if name in SKIP_DIRS:
                continue
            if name.startswith(".") and name not in KEEP_DOT_DIRS:
                continue
            if name == "skills" and current.name in WORKSPACE_PARENTS:
                found.append(entry)
            if depth < SCAN_MAX_DEPTH:
                stack.append((entry, depth + 1))
    return found


def _plugin_skill_dirs(deadline: float) -> list[Path]:
    found: list[Path] = []
    plugin_root = os.environ.get("CURSOR_PLUGIN_ROOT")
    search = []
    if plugin_root:
        search.append(Path(plugin_root))
    search.append(Path.home() / ".cursor" / "plugins")
    for base in search:
        if time.monotonic() >= deadline:
            break
        if not base.is_dir():
            continue
        found.extend(_walk_plugin_skill_dirs(base, deadline))
    return found


def _walk_plugin_skill_dirs(base: Path, deadline: float) -> list[Path]:
    found: list[Path] = []
    stack = [(base, 0)]
    while stack and time.monotonic() < deadline:
        current, depth = stack.pop()
        if depth > SCAN_MAX_DEPTH:
            continue
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if time.monotonic() >= deadline:
                break
            if not entry.is_dir():
                continue
            name = entry.name
            if name in SKIP_DIRS:
                continue
            if name.startswith(".") and name not in KEEP_DOT_DIRS:
                continue
            if name == "skills":
                found.append(entry)
            if depth < SCAN_MAX_DEPTH:
                stack.append((entry, depth + 1))
    return found


def _scan_skills(roots: list[tuple[Path, str]], deadline: float | None = None) -> tuple[dict[str, str], int, bool]:
    providers: dict[str, str] = {}
    offered = False
    # Directory walks already spent SCAN_BUDGET_S. Listing collected roots
    # gets a fresh window so a slow plugin tree cannot skip workspace skills.
    deadline = time.monotonic() + SCAN_BUDGET_S
    for root, provider in roots:
        if time.monotonic() >= deadline:
            break
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            if time.monotonic() >= deadline:
                break
            skill_md = entry / "SKILL.md"
            if not entry.is_dir() or not skill_md.is_file():
                continue
            name = entry.name.lower()
            if name in providers:
                _debug(f"collision {name} {provider} ignored, kept {providers[name]}")
                continue
            providers[name] = provider
            if not _disabled_model(skill_md):
                offered = True
    return providers, len(providers), offered


def _disabled_model(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            raw = handle.read(SKILL_HEAD_BYTES)
    except OSError:
        return False
    text = raw.decode("utf-8", errors="replace")
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    front = text[3:end] if end != -1 else text[:256]
    return bool(DISABLED_MODEL.search(front))


def _attachment_skills(attachments: Any, roots: list[tuple[Path, str]]) -> list[tuple[str, str]]:
    if not isinstance(attachments, list):
        return []
    found: list[tuple[str, str]] = []
    for item in attachments:
        if not isinstance(item, dict):
            continue
        file_path = item.get("file_path")
        if not isinstance(file_path, str):
            continue
        classified = classify_skill_path(file_path, roots)
        if classified is not None:
            found.append(classified)
    return found


def _record_subagent(state_dir: Path, payload: dict[str, Any], parent_id: str) -> None:
    subagent_id = payload.get("subagent_id")
    if not isinstance(subagent_id, str) or not subagent_id:
        return
    model = payload.get("subagent_model") or "unknown"

    def _update() -> None:
        index = _load_subagents(state_dir)
        index[subagent_id] = {
            "parent": parent_id,
            "model": model,
            "at": _now_ns(),
        }
        _atomic_write(state_dir / "subagents.json", json.dumps(index, separators=(",", ":")))

    _with_lock(state_dir / "subagents.lock", _update)


def _load_subagents(state_dir: Path) -> dict[str, Any]:
    path = state_dir / "subagents.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _load_state(path: Path) -> State | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return _state_from_dict(raw)
    except (TypeError, ValueError):
        return None


def _state_from_dict(raw: dict[str, Any]) -> State:
    return State(
        version=int(raw.get("version") or STATE_VERSION),
        harness=str(raw.get("harness") or "cursor"),
        conversation_id=str(raw.get("conversation_id") or ""),
        started_at_unix_nano=int(raw.get("started_at_unix_nano") or 0),
        model=str(raw.get("model") or "unknown"),
        repo=str(raw.get("repo") or "none"),
        is_subagent=bool(raw.get("is_subagent")),
        parent_conversation_id=raw.get("parent_conversation_id"),
        offered=bool(raw.get("offered")),
        discovered_count=int(raw.get("discovered_count") or 0),
        discovered_emitted=bool(raw.get("discovered_emitted")),
        providers=dict(raw.get("providers") or {}),
        user_this_turn=list(raw.get("user_this_turn") or []),
        stops_seen=int(raw.get("stops_seen") or 0),
        series=dict(raw.get("series") or {}),
    )


def _state_to_dict(state: State) -> dict[str, Any]:
    return {
        "version": state.version,
        "harness": state.harness,
        "conversation_id": state.conversation_id,
        "started_at_unix_nano": state.started_at_unix_nano,
        "model": state.model,
        "repo": state.repo,
        "is_subagent": state.is_subagent,
        "parent_conversation_id": state.parent_conversation_id,
        "offered": state.offered,
        "discovered_count": state.discovered_count,
        "discovered_emitted": state.discovered_emitted,
        "providers": state.providers,
        "user_this_turn": state.user_this_turn,
        "stops_seen": state.stops_seen,
        "series": state.series,
    }


def _state_dir() -> Path | None:
    for path in _state_dir_candidates():
        if _ensure_state_dir(path):
            return path
    raw = (os.environ.get("TMPDIR") or os.environ.get("TEMP") or os.environ.get("TMP") or "").strip()
    tmp = Path(raw) if raw else Path(tempfile.gettempdir())
    fallback = tmp / f"skill-telemetry-{os.getuid()}"
    return fallback if _ensure_state_dir(fallback) else None


def _state_dir_candidates() -> list[Path]:
    found: list[Path] = []
    override = (os.environ.get("SKILL_TELEMETRY_STATE_DIR") or "").strip()
    if override:
        found.append(Path(override))
    xdg = (os.environ.get("XDG_CACHE_HOME") or "").strip()
    if xdg:
        found.append(Path(xdg) / "skill-telemetry")
    home = (os.environ.get("HOME") or "").strip()
    if home:
        found.append(Path(home) / ".cache" / "skill-telemetry")
    return found


def _ensure_state_dir(path: Path) -> bool:
    try:
        if path.exists() or path.is_symlink():
            if not _owned_dir(path):
                return False
        else:
            path.mkdir(parents=True, exist_ok=True, mode=STATE_DIR_MODE)
        if not _owned_dir(path):
            return False
        os.chmod(path, STATE_DIR_MODE)
        probe = path / ".writable"
        probe.write_text("")
        probe.unlink()
        return True
    except OSError:
        return False


def _owned_dir(path: Path) -> bool:
    try:
        st = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        return False
    return st.st_uid == os.getuid()


def _with_lock(lock_path: Path, fn: Any) -> Any:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        try:
            os.chmod(lock_path, STATE_FILE_MODE)
        except OSError:
            pass
        deadline = time.time() + LOCK_WAIT_S
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() >= deadline:
                    _debug("lock timeout")
                    return None
                time.sleep(LOCK_RETRY_S)
        try:
            return fn()
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _atomic_write(path: Path, text: str) -> None:
    tmp = Path(str(path) + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, STATE_FILE_MODE)
    try:
        os.write(fd, text.encode("utf-8"))
        os.fchmod(fd, STATE_FILE_MODE)
    finally:
        os.close(fd)
    os.replace(tmp, path)


def _maybe_gc(state_dir: Path, now: float, *, force: bool) -> None:
    lock_path = state_dir / "gc.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        try:
            os.chmod(lock_path, STATE_FILE_MODE)
        except OSError:
            pass
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            _gc_pass(state_dir, now, force=force)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _gc_pass(state_dir: Path, now: float, *, force: bool) -> None:
    marker = state_dir / "gc"
    if not force:
        try:
            if now - marker.stat().st_mtime < GC_INTERVAL_S:
                return
        except OSError:
            pass
    cutoff = now - TTL_S
    try:
        entries = list(state_dir.iterdir())
    except OSError:
        return
    unlinked = 0
    hit_cap = False
    for path in entries:
        if path.name in GC_SKIP_NAMES or path.suffix not in GC_UNLINK_SUFFIXES:
            continue
        try:
            if path.stat().st_mtime >= cutoff:
                continue
            if unlinked >= GC_MAX_UNLINKS:
                hit_cap = True
                break
            path.unlink()
            unlinked += 1
        except OSError:
            continue
    if hit_cap:
        return
    try:
        _atomic_write(marker, str(int(now)))
    except OSError:
        return


def _export_state(state: State, mode: str, state_dir: Path) -> None:
    service = (os.environ.get("OTEL_SERVICE_NAME") or "").strip()
    blob = encode_snapshot(state, now_ns=_now_ns(), service_name=service, harness=mode)
    if os.environ.get("SKILL_TELEMETRY_SYNC_EXPORT") == "1":
        _post_otlp(blob)
        return
    claim = _claim_export(state_dir, state.conversation_id)
    if claim is None:
        _mark_export_dirty(state_dir, state.conversation_id)
        return
    fd, name = tempfile.mkstemp(prefix="skill-telemetry-", suffix=".pb")
    os.close(fd)
    try:
        Path(name).write_bytes(blob)
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--export", name, str(claim)],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        _debug(f"export spawn: {exc}")
        _unlink_quiet(Path(name))
        _unlink_quiet(claim)


def _claim_export(state_dir: Path, session_id: str) -> Path | None:
    """Exclusive per-session export slot. None means skip and mark dirty."""
    path = _state_child(state_dir, session_id, ".exporting")
    if path is None:
        return None
    if _export_in_flight(path):
        return None
    try:
        path.unlink()
    except OSError:
        pass
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, STATE_FILE_MODE)
    except FileExistsError:
        return None
    except OSError:
        return None
    try:
        os.fchmod(fd, STATE_FILE_MODE)
    finally:
        os.close(fd)
    return path


def _export_in_flight(path: Path) -> bool:
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age < (_timeout_ms() / 1000.0) + EXPORT_CLAIM_GRACE_S


def _export_file(path: str, claim: str = "") -> None:
    target = Path(path)
    try:
        try:
            blob = target.read_bytes()
        except OSError as exc:
            _debug(f"export read: {exc}")
            return
        _post_snapshot_until_clean(blob, claim)
    finally:
        _unlink_quiet(target)
        _unlink_export_claim(claim)
        _export_if_dirty(claim)


def _post_snapshot_until_clean(blob: bytes, claim: str) -> None:
    while True:
        _post_otlp(blob)
        if not _consume_export_dirty(claim):
            return
        follow = _snapshot_for_claim(claim)
        if follow is None:
            return
        blob = follow


def _mark_export_dirty(state_dir: Path, session_id: str) -> None:
    path = _state_child(state_dir, session_id, ".dirty")
    if path is None:
        return
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT, STATE_FILE_MODE)
    except OSError:
        return
    try:
        os.fchmod(fd, STATE_FILE_MODE)
    finally:
        os.close(fd)


def _consume_export_dirty(raw: str) -> bool:
    located = _export_session_dir(raw)
    if located is None:
        return False
    state_dir, session_id = located
    path = _state_child(state_dir, session_id, ".dirty")
    if path is None:
        return False
    try:
        path.unlink()
        return True
    except OSError:
        return False


def _snapshot_for_claim(raw: str) -> bytes | None:
    located = _export_session_dir(raw)
    if located is None:
        return None
    state_dir, session_id = located
    path = _state_child(state_dir, session_id, ".json")
    if path is None:
        return None
    state = _load_state(path)
    if state is None or not state.series:
        return None
    service = (os.environ.get("OTEL_SERVICE_NAME") or "").strip()
    return encode_snapshot(state, now_ns=_now_ns(), service_name=service, harness=state.harness)


def _export_if_dirty(raw: str) -> None:
    located = _export_session_dir(raw)
    if located is None:
        return
    state_dir, session_id = located
    dirty = _state_child(state_dir, session_id, ".dirty")
    if dirty is None or not dirty.is_file():
        return
    held = _claim_export(state_dir, session_id)
    if held is None:
        return
    try:
        blob = _snapshot_for_claim(str(held))
        if blob is None:
            return
        _post_snapshot_until_clean(blob, str(held))
    finally:
        _unlink_quiet(held)


def _export_session_dir(raw: str) -> tuple[Path, str] | None:
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.suffix != ".exporting" or not _valid_id(candidate.stem):
        return None
    resolved = _resolve(candidate)
    state_dir = resolved.parent
    if not _owned_dir(state_dir):
        return None
    expected = _state_child(state_dir, candidate.stem, ".exporting")
    if expected is None or resolved != expected:
        return None
    return state_dir, candidate.stem


def _unlink_export_claim(raw: str) -> None:
    located = _export_session_dir(raw)
    if located is None:
        return
    expected = _state_child(located[0], located[1], ".exporting")
    if expected is None:
        return
    _unlink_quiet(expected)


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        return


def _post_otlp(blob: bytes) -> None:
    url = _metrics_url()
    if not url:
        return
    timeout_ms = _timeout_ms()
    request = urllib.request.Request(url, data=blob, method="POST")
    request.add_header("Content-Type", "application/x-protobuf")
    for key, value in _otlp_headers():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout_ms / 1000.0) as response:
            response.read()
        _debug(f"export ok {url}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        _debug(f"export fail {exc}")


def _metrics_url() -> str | None:
    metrics = (os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT") or "").strip()
    if metrics:
        return metrics
    endpoint = (os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip()
    if not endpoint:
        return None
    return endpoint.rstrip("/") + "/v1/metrics"


def _timeout_ms() -> int:
    raw = os.environ.get("OTEL_EXPORTER_OTLP_TIMEOUT")
    if raw is None or not raw.strip():
        return DEFAULT_TIMEOUT_MS
    try:
        value = int(raw.strip())
    except ValueError:
        return DEFAULT_TIMEOUT_MS
    return value if value > 0 else DEFAULT_TIMEOUT_MS


def _otlp_headers() -> list[tuple[str, str]]:
    raw = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS") or ""
    headers: list[tuple[str, str]] = []
    for part in raw.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        headers.append((urllib.parse.unquote(key.strip()), urllib.parse.unquote(value.strip())))
    return headers


def _now_ns() -> int:
    return time.time_ns()


def _resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def _relative_to(path: Path, root: Path) -> Path | None:
    try:
        return path.relative_to(root)
    except ValueError:
        return None


def _debug(message: str) -> None:
    if os.environ.get("SKILL_TELEMETRY_DEBUG") != "1":
        return
    try:
        directory = _state_dir()
        if directory is None:
            return
        with (directory / "debug.log").open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except OSError:
        return


def _varint(n: int) -> bytes:
    if n < 0:
        n = n & ((1 << 64) - 1)
    out = bytearray()
    while n > 0x7F:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def _key(field: int, wire: int) -> bytes:
    return _varint((field << 3) | wire)


def _len_field(field: int, data: bytes) -> bytes:
    return _key(field, 2) + _varint(len(data)) + data


def _var_field(field: int, n: int) -> bytes:
    return _key(field, 0) + _varint(n)


def _fixed64(field: int, n: int) -> bytes:
    return _key(field, 1) + struct.pack("<Q", n & 0xFFFFFFFFFFFFFFFF)


def _sfixed64(field: int, n: int) -> bytes:
    return _key(field, 1) + struct.pack("<q", n)


def _string_field(field: int, value: str) -> bytes:
    encoded = value.encode("utf-8")
    return _len_field(field, encoded)


def _any_value(value: AttrValue) -> bytes:
    if isinstance(value, bool):
        return _var_field(2, 1 if value else 0)
    return _string_field(1, str(value))


def _kv(key: str, value: AttrValue) -> bytes:
    return _string_field(1, key) + _len_field(2, _any_value(value))


def _resource(attrs: list[tuple[str, str]]) -> bytes:
    return b"".join(_len_field(1, _kv(key, value)) for key, value in attrs)


def _number_point(attrs: Attrs, start_ns: int, now_ns: int, value: int) -> bytes:
    encoded_attrs = b"".join(_len_field(7, _kv(key, attrs[key])) for key in sorted(attrs))
    return _fixed64(2, start_ns) + _fixed64(3, now_ns) + _sfixed64(6, value) + encoded_attrs


def _metric(name: str, description: str, unit: str, points: list[bytes], monotonic: bool) -> bytes:
    encoded_sum = (
        b"".join(_len_field(1, point) for point in points) + _var_field(2, 2) + _var_field(3, 1 if monotonic else 0)
    )
    return _string_field(1, name) + _string_field(2, description) + _string_field(3, unit) + _len_field(7, encoded_sum)


if __name__ == "__main__":
    raise SystemExit(main())
