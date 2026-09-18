"""Unit and fixture tests for the skill-telemetry hook."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
HOOK_PY = REPO / "hooks" / "skill-telemetry" / "skill_telemetry.py"
HOOK_SH = REPO / "hooks" / "skill-telemetry" / "skill-telemetry"
FIXTURES = Path(__file__).parent / "fixtures" / "skill-telemetry"
BOM = b"\xef\xbb\xbf"

ATTRS = {
    "agent.session.id": "s1",
    "gen_ai.request.model": "test-model",
    "vcs.repository.name": "loadout",
    "agent.is_subagent": False,
}
PROVIDERS = {"foo": "claude", "bar": "workspace"}


def load_hook():
    spec = importlib.util.spec_from_file_location("skill_telemetry_hook", HOOK_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook():
    return load_hook()


@pytest.fixture
def telemetry_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    state = tmp_path / "state"
    home = tmp_path / "home"
    home.mkdir()
    workspace = tmp_path / "ws"
    _write_workspace(workspace)
    monkeypatch.setenv("SKILL_TELEMETRY_STATE_DIR", str(state))
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:1")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "loadout-tests")
    monkeypatch.setenv("SKILL_TELEMETRY_SYNC_EXPORT", "1")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "50")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_PROTOCOL", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)
    monkeypatch.delenv("SKILL_TELEMETRY_ASSUME_ROOT", raising=False)
    monkeypatch.setenv("SKILL_TELEMETRY_ENABLED", "true")
    return {"state": state, "ws": workspace, "home": home, "project": tmp_path / "project"}


def _write_workspace(workspace: Path, *, extra_skills: dict[str, str] | None = None) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    git = workspace / ".git"
    git.mkdir(exist_ok=True)
    (git / "config").write_text('[remote "origin"]\n\turl = https://github.com/sazlin/loadout.git\n')
    skills = extra_skills or {"foo": "---\nname: foo\ndescription: d\n---\n\n# Foo\n"}
    for name, body in skills.items():
        dest = workspace / ".claude" / "skills" / name
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_text(body)


def _payload(event: str, workspace: Path, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "conversation_id": "conv-1",
        "generation_id": "gen-1",
        "model": "test-model",
        "hook_event_name": event,
        "workspace_roots": [str(workspace)],
    }
    body.update(extra)
    return body


def _run(hook: Any, telemetry_env: dict[str, Path], payload: dict[str, Any], mode: str = "cursor") -> str:
    raw = json.dumps(payload).encode()
    import sys
    from io import StringIO

    captured = StringIO()
    old = sys.stdout
    sys.stdout = captured
    try:
        rc = hook.main([mode], stdin=raw)
    finally:
        sys.stdout = old
    assert rc == 0
    return captured.getvalue()


def _state(telemetry_env: dict[str, Path], session: str = "conv-1") -> dict[str, Any]:
    path = telemetry_env["state"] / f"{session}.json"
    return json.loads(path.read_text())


def _series_value(state: dict[str, Any], instrument: str, **attrs: str) -> int:
    for key, value in state["series"].items():
        if not key.startswith(instrument + "|"):
            continue
        if all(f"{name}={item}" in key.split("|") for name, item in attrs.items()):
            return int(value)
    return 0


def test_decide_session_start_records_discovered_and_skips_subagent(hook: Any) -> None:
    parent = hook.State()
    rows = hook.decide(
        parent,
        {"type": "session_start", "skillCount": 2, "offered": True, "providers": PROVIDERS, "subagent": False},
        ATTRS,
    )
    assert rows[0].instrument == hook.DISCOVERED
    assert rows[0].value == 2
    child = hook.State()
    assert (
        hook.decide(
            child,
            {"type": "session_start", "skillCount": 2, "offered": True, "providers": PROVIDERS, "subagent": True},
            {**ATTRS, "agent.is_subagent": True},
        )
        == []
    )


def test_decide_turns_increment_when_offered_and_omit_skill_name(hook: Any) -> None:
    state = hook.State()
    hook.decide(
        state,
        {"type": "session_start", "skillCount": 2, "offered": True, "providers": PROVIDERS, "subagent": False},
        ATTRS,
    )
    rows = hook.decide(state, {"type": "turn_end"}, ATTRS)
    assert len(rows) == 1
    assert rows[0].instrument == hook.TURNS
    assert "skill.name" not in rows[0].attributes


def test_decide_turns_empty_catalog_emits_nothing(hook: Any) -> None:
    state = hook.State()
    hook.decide(
        state,
        {"type": "session_start", "skillCount": 0, "offered": False, "providers": {}, "subagent": False},
        ATTRS,
    )
    assert hook.decide(state, {"type": "turn_end"}, ATTRS) == []


def test_decide_user_then_model_read_is_one_read(hook: Any) -> None:
    state = hook.State()
    hook.decide(
        state,
        {"type": "session_start", "skillCount": 1, "offered": True, "providers": PROVIDERS, "subagent": False},
        ATTRS,
    )
    hook.decide(state, {"type": "turn_start"}, ATTRS)
    user = hook.decide(state, {"type": "user_skill", "name": "foo"}, ATTRS)
    assert user[0].attributes["skill.invocation_kind"] == "user"
    assert hook.decide(state, {"type": "model_read", "name": "foo", "asset": False, "error": False}, ATTRS) == []


def test_decide_autoload_never_used_on_cursor_events(hook: Any, telemetry_env: dict[str, Path]) -> None:
    workspace = telemetry_env["ws"]
    _run(hook, telemetry_env, _payload("sessionStart", workspace))
    _run(
        hook,
        telemetry_env,
        _payload(
            "beforeReadFile",
            workspace,
            file_path=str(workspace / ".claude/skills/foo/SKILL.md"),
        ),
    )
    state = _state(telemetry_env)
    blob = json.dumps(state["series"])
    assert "autoload" not in blob


@pytest.mark.parametrize(
    ("rel", "provider"),
    [
        (".claude/skills/foo/SKILL.md", "claude"),
        (".cursor/skills/foo/SKILL.md", "workspace"),
        (".agents/skills/foo/SKILL.md", "workspace"),
        (".codex/skills/foo/SKILL.md", "codex"),
    ],
)
def test_classify_skill_body_under_each_root(hook: Any, tmp_path: Path, rel: str, provider: str) -> None:
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text("# skill\n")
    roots = [
        (tmp_path / ".cursor" / "skills", "workspace"),
        (tmp_path / ".agents" / "skills", "workspace"),
        (tmp_path / ".claude" / "skills", "claude"),
        (tmp_path / ".codex" / "skills", "codex"),
    ]
    assert hook.classify_skill_path(str(path), roots) == ("foo", provider)


def test_classify_ignores_references_and_outside_roots(hook: Any, tmp_path: Path) -> None:
    roots = [(tmp_path / ".claude" / "skills", "claude")]
    (tmp_path / ".claude" / "skills" / "foo").mkdir(parents=True)
    asset = tmp_path / ".claude" / "skills" / "foo" / "references" / "x.md"
    asset.parent.mkdir()
    asset.write_text("nope")
    outside = tmp_path / "skills" / "foo" / "SKILL.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("# src\n")
    assert hook.classify_skill_path(str(asset), roots) is None
    assert hook.classify_skill_path(str(outside), roots) is None


def test_classify_lowercases_and_longest_root_wins(hook: Any, tmp_path: Path) -> None:
    nested = tmp_path / "proj" / ".cursor" / "skills"
    nested.mkdir(parents=True)
    path = nested / "Foo" / "SKILL.md"
    path.parent.mkdir()
    path.write_text("# x\n")
    roots = [
        (tmp_path / "proj", "unknown"),
        (nested, "workspace"),
    ]
    assert hook.classify_skill_path(str(path), roots) == ("foo", "workspace")


def test_prompt_parsing_known_names_only(hook: Any) -> None:
    known = {"foo"}
    assert hook.parse_prompt_skill_names("/foo", known) == ["foo"]
    assert hook.parse_prompt_skill_names("text /foo more", known) == ["foo"]
    assert hook.parse_prompt_skill_names("/foo/bar", known) == []
    assert hook.parse_prompt_skill_names("/unknown", known) == []
    assert hook.parse_prompt_skill_names("!cmd /foo", known) == []


def test_session_start_emits_discovered_for_root(hook: Any, telemetry_env: dict[str, Path]) -> None:
    stdout = _run(hook, telemetry_env, _payload("sessionStart", telemetry_env["ws"]))
    assert json.loads(stdout) == {}
    state = _state(telemetry_env)
    assert state["discovered_count"] == 1
    assert state["offered"] is True
    assert _series_value(state, "skill.discovered_on_session_start") == 1
    assert "skill.name=" not in "".join(state["series"])


def test_read_skill_body_counts_model_kind(hook: Any, telemetry_env: dict[str, Path]) -> None:
    workspace = telemetry_env["ws"]
    _run(hook, telemetry_env, _payload("sessionStart", workspace))
    stdout = _run(
        hook,
        telemetry_env,
        _payload("beforeReadFile", workspace, file_path=str(workspace / ".claude/skills/foo/SKILL.md")),
    )
    assert json.loads(stdout) == {"permission": "allow"}
    state = _state(telemetry_env)
    assert _series_value(state, "skill.reads", **{"skill.name": "foo", "skill.invocation_kind": "model"}) == 1
    assert _series_value(state, "skill.reads", **{"skill.provider": "claude"}) == 1


def test_read_reference_and_source_skill_md_are_ignored(hook: Any, telemetry_env: dict[str, Path]) -> None:
    workspace = telemetry_env["ws"]
    ref = workspace / ".claude" / "skills" / "foo" / "references" / "x.md"
    ref.parent.mkdir()
    ref.write_text("nope")
    source = workspace / "skills" / "foo" / "SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("# src\n")
    _run(hook, telemetry_env, _payload("sessionStart", workspace))
    _run(hook, telemetry_env, _payload("beforeReadFile", workspace, file_path=str(ref)))
    _run(hook, telemetry_env, _payload("beforeReadFile", workspace, file_path=str(source)))
    state = _state(telemetry_env)
    assert _series_value(state, "skill.reads") == 0


def test_user_slash_then_same_turn_read_is_one(hook: Any, telemetry_env: dict[str, Path]) -> None:
    workspace = telemetry_env["ws"]
    _run(hook, telemetry_env, _payload("sessionStart", workspace))
    stdout = _run(
        hook,
        telemetry_env,
        _payload("beforeSubmitPrompt", workspace, prompt="/foo do the thing"),
    )
    assert json.loads(stdout) == {"continue": True}
    _run(
        hook,
        telemetry_env,
        _payload("beforeReadFile", workspace, file_path=str(workspace / ".claude/skills/foo/SKILL.md")),
    )
    state = _state(telemetry_env)
    assert _series_value(state, "skill.reads", **{"skill.invocation_kind": "user"}) == 1
    assert _series_value(state, "skill.reads", **{"skill.invocation_kind": "model"}) == 0


def test_next_turn_model_read_counts_again(hook: Any, telemetry_env: dict[str, Path]) -> None:
    workspace = telemetry_env["ws"]
    _run(hook, telemetry_env, _payload("sessionStart", workspace))
    _run(hook, telemetry_env, _payload("beforeSubmitPrompt", workspace, prompt="/foo"))
    _run(hook, telemetry_env, _payload("stop", workspace, status="completed", loop_count=0))
    _run(
        hook,
        telemetry_env,
        _payload("beforeReadFile", workspace, file_path=str(workspace / ".claude/skills/foo/SKILL.md")),
    )
    state = _state(telemetry_env)
    assert _series_value(state, "skill.reads", **{"skill.invocation_kind": "user"}) == 1
    assert _series_value(state, "skill.reads", **{"skill.invocation_kind": "model"}) == 1
    assert _series_value(state, "skill.turns") == 1


def test_stop_empty_catalog_emits_no_turn(hook: Any, telemetry_env: dict[str, Path]) -> None:
    workspace = telemetry_env["ws"]
    empty = workspace / "empty"
    empty.mkdir()
    (empty / ".git").mkdir()
    stdout = _run(hook, telemetry_env, _payload("sessionStart", empty, conversation_id="empty-1"))
    _run(hook, telemetry_env, _payload("stop", empty, conversation_id="empty-1", status="completed"))
    assert json.loads(stdout) == {}
    state = _state(telemetry_env, "empty-1")
    assert _series_value(state, "skill.turns") == 0


def test_cli_session_end_fallback_one_turn(hook: Any, telemetry_env: dict[str, Path]) -> None:
    workspace = telemetry_env["ws"]
    _run(hook, telemetry_env, _payload("sessionStart", workspace))
    _run(hook, telemetry_env, _payload("sessionEnd", workspace, reason="completed"))
    state = _state(telemetry_env)
    assert _series_value(state, "skill.turns") == 1
    _run(hook, telemetry_env, _payload("sessionEnd", workspace, reason="completed"))
    state = _state(telemetry_env)
    assert _series_value(state, "skill.turns") == 1


def test_cli_session_end_skips_when_stop_already_counted(hook: Any, telemetry_env: dict[str, Path]) -> None:
    workspace = telemetry_env["ws"]
    _run(hook, telemetry_env, _payload("sessionStart", workspace))
    _run(hook, telemetry_env, _payload("stop", workspace, status="completed"))
    _run(hook, telemetry_env, _payload("sessionEnd", workspace, reason="completed"))
    assert _series_value(_state(telemetry_env), "skill.turns") == 1


def test_unknown_desktop_session_does_not_emit_discovered(hook: Any, telemetry_env: dict[str, Path]) -> None:
    workspace = telemetry_env["ws"]
    _run(
        hook,
        telemetry_env,
        _payload("beforeReadFile", workspace, file_path=str(workspace / ".claude/skills/foo/SKILL.md")),
    )
    state = _state(telemetry_env)
    assert _series_value(state, "skill.discovered_on_session_start") == 0
    assert _series_value(state, "skill.reads") == 1


def test_unknown_bc_session_emits_discovered(hook: Any, telemetry_env: dict[str, Path]) -> None:
    workspace = telemetry_env["ws"]
    session = "bc-cloud-root"
    _run(
        hook,
        telemetry_env,
        _payload(
            "beforeReadFile",
            workspace,
            conversation_id=session,
            file_path=str(workspace / ".claude/skills/foo/SKILL.md"),
        ),
    )
    state = _state(telemetry_env, session)
    assert _series_value(state, "skill.discovered_on_session_start") == 1
    assert state["is_subagent"] is False


def test_linked_child_is_subagent_and_skips_discovered(hook: Any, telemetry_env: dict[str, Path]) -> None:
    workspace = telemetry_env["ws"]
    _run(hook, telemetry_env, _payload("sessionStart", workspace))
    _run(
        hook,
        telemetry_env,
        _payload(
            "subagentStart",
            workspace,
            subagent_id="child-1",
            parent_conversation_id="conv-1",
            subagent_model="child-model",
        ),
    )
    _run(
        hook,
        telemetry_env,
        _payload(
            "beforeReadFile",
            workspace,
            conversation_id="child-1",
            file_path=str(workspace / ".claude/skills/foo/SKILL.md"),
        ),
    )
    child = _state(telemetry_env, "child-1")
    assert child["is_subagent"] is True
    assert _series_value(child, "skill.discovered_on_session_start") == 0
    assert _series_value(child, "skill.reads") == 1


@pytest.mark.parametrize("flag", ["", "  ", None])
def test_missing_endpoint_is_noop(
    hook: Any, telemetry_env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, flag: str | None
) -> None:
    if flag is None:
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    else:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", flag)
    opened = {"n": 0}

    def boom(*_args: Any, **_kwargs: Any) -> None:
        opened["n"] += 1
        raise AssertionError("urlopen")

    monkeypatch.setattr(hook.urllib.request, "urlopen", boom)
    stdout = _run(hook, telemetry_env, _payload("sessionStart", telemetry_env["ws"]))
    assert json.loads(stdout) == {}
    assert not telemetry_env["state"].exists()
    assert opened["n"] == 0


def test_missing_service_name_is_noop(
    hook: Any, telemetry_env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    stdout = _run(hook, telemetry_env, _payload("beforeReadFile", telemetry_env["ws"], file_path="/tmp/x"))
    assert json.loads(stdout) == {"permission": "allow"}
    assert not telemetry_env["state"].exists()


def test_disabled_and_non_protobuf_are_noop(
    hook: Any, telemetry_env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SKILL_TELEMETRY_ENABLED", "false")
    _run(hook, telemetry_env, _payload("sessionStart", telemetry_env["ws"]))
    assert not telemetry_env["state"].exists()
    monkeypatch.setenv("SKILL_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/json")
    _run(hook, telemetry_env, _payload("sessionStart", telemetry_env["ws"]))
    assert not telemetry_env["state"].exists()


def test_bom_one_and_two_still_parse(hook: Any, telemetry_env: dict[str, Path]) -> None:
    payload = _payload("sessionStart", telemetry_env["ws"])
    raw = BOM + BOM + json.dumps(payload).encode()
    import sys
    from io import StringIO

    captured = StringIO()
    old = sys.stdout
    sys.stdout = captured
    try:
        assert hook.main(["cursor"], stdin=raw) == 0
    finally:
        sys.stdout = old
    assert json.loads(captured.getvalue()) == {}
    assert _state(telemetry_env)["discovered_count"] == 1


def test_no_file_created_under_project_root(
    hook: Any, telemetry_env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = telemetry_env["project"]
    project.mkdir()
    monkeypatch.chdir(project)
    before = {path.relative_to(project) for path in project.rglob("*")}
    _run(hook, telemetry_env, _payload("sessionStart", telemetry_env["ws"]))
    _run(
        hook,
        telemetry_env,
        _payload(
            "beforeReadFile", telemetry_env["ws"], file_path=str(telemetry_env["ws"] / ".claude/skills/foo/SKILL.md")
        ),
    )
    after = {path.relative_to(project) for path in project.rglob("*")}
    assert after == before


def test_ttl_removes_eight_day_old_state(hook: Any, telemetry_env: dict[str, Path]) -> None:
    stale = telemetry_env["state"]
    stale.mkdir()
    old = stale / "old.json"
    old.write_text("{}")
    age = time.time() - 8 * 24 * 3600
    os.utime(old, (age, age))
    _run(hook, telemetry_env, _payload("sessionStart", telemetry_env["ws"]))
    assert not old.exists()


def test_cumulative_across_processes(telemetry_env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[bytes] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            captured.append(self.rfile.read(length))
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            del format, args

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "api-key=secret%2Fvalue")
    workspace = telemetry_env["ws"]
    payload = _payload("beforeReadFile", workspace, file_path=str(workspace / ".claude/skills/foo/SKILL.md"))
    env = os.environ.copy()
    for _ in range(2):
        result = subprocess.run(
            ["python3", str(HOOK_PY), "cursor"],
            input=json.dumps(payload).encode(),
            capture_output=True,
            check=False,
            env=env,
        )
        assert result.returncode == 0
    server.shutdown()
    assert len(captured) == 2
    from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest

    starts = []
    values = []
    for blob in captured:
        request = ExportMetricsServiceRequest()
        request.ParseFromString(blob)
        metric = next(
            m for sm in request.resource_metrics[0].scope_metrics for m in sm.metrics if m.name == "skill.reads"
        )
        point = metric.sum.data_points[0]
        starts.append(point.start_time_unix_nano)
        values.append(point.as_int)
    assert starts[0] == starts[1]
    assert values == [1, 2]


def test_protobuf_snapshot_decodes(hook: Any) -> None:
    from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
    from opentelemetry.proto.metrics.v1.metrics_pb2 import AggregationTemporality

    state = hook.State(
        conversation_id="s1",
        started_at_unix_nano=100,
        model="test-model",
        repo="loadout",
        series={
            "skill.reads|agent.is_subagent=false|agent.session.id=s1|gen_ai.request.model=test-model|skill.invocation_kind=model|skill.name=foo|skill.provider=claude|vcs.repository.name=loadout": 3,
            "skill.turns|agent.is_subagent=false|agent.session.id=s1|gen_ai.request.model=test-model|vcs.repository.name=loadout": 2,
            "skill.discovered_on_session_start|agent.is_subagent=false|agent.session.id=s1|gen_ai.request.model=test-model|vcs.repository.name=loadout": 4,
        },
    )
    blob = hook.encode_snapshot(state, now_ns=200, service_name="svc", harness="cursor")
    request = ExportMetricsServiceRequest()
    request.ParseFromString(blob)
    resource = {attr.key: attr.value.string_value for attr in request.resource_metrics[0].resource.attributes}
    assert resource["service.name"] == "svc"
    assert resource["telemetry.sdk.name"] == "skill-telemetry-hook"
    scope = request.resource_metrics[0].scope_metrics[0].scope
    assert scope.name == "cursor.skill-telemetry"
    by_name = {metric.name: metric for metric in request.resource_metrics[0].scope_metrics[0].metrics}
    assert by_name["skill.reads"].unit == "{read}"
    assert by_name["skill.turns"].unit == "{turn}"
    assert by_name["skill.discovered_on_session_start"].unit == "{skill}"
    assert (
        by_name["skill.reads"].sum.aggregation_temporality == AggregationTemporality.AGGREGATION_TEMPORALITY_CUMULATIVE
    )
    assert by_name["skill.reads"].sum.is_monotonic is True
    assert by_name["skill.discovered_on_session_start"].sum.is_monotonic is False
    read = by_name["skill.reads"].sum.data_points[0]
    assert read.start_time_unix_nano == 100
    assert read.time_unix_nano == 200
    assert read.as_int == 3
    keys = {attr.key: attr.value for attr in read.attributes}
    assert keys["skill.name"].string_value == "foo"
    assert keys["agent.is_subagent"].bool_value is False


def test_exporter_headers_and_path(hook: Any, telemetry_env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            seen["path"] = self.path
            seen["ctype"] = self.headers.get("Content-Type")
            seen["api"] = self.headers.get("api-key")
            length = int(self.headers.get("Content-Length", "0"))
            seen["body"] = self.rfile.read(length)
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            del format, args

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "api-key=secret")
    _run(hook, telemetry_env, _payload("sessionStart", telemetry_env["ws"]))
    server.shutdown()
    assert seen["path"] == "/v1/metrics"
    assert seen["ctype"] == "application/x-protobuf"
    assert seen["api"] == "secret"
    assert seen["body"]


def test_unreachable_endpoint_returns_quickly(hook: Any, telemetry_env: dict[str, Path]) -> None:
    started = time.monotonic()
    stdout = _run(
        hook,
        telemetry_env,
        _payload(
            "beforeReadFile", telemetry_env["ws"], file_path=str(telemetry_env["ws"] / ".claude/skills/foo/SKILL.md")
        ),
    )
    elapsed = time.monotonic() - started
    assert json.loads(stdout) == {"permission": "allow"}
    assert elapsed < 1.0


def test_concurrency_loses_no_increments(telemetry_env: dict[str, Path]) -> None:
    workspace = telemetry_env["ws"]
    payload = json.dumps(
        _payload("beforeReadFile", workspace, file_path=str(workspace / ".claude/skills/foo/SKILL.md"))
    ).encode()
    env = os.environ.copy()
    procs = [
        subprocess.Popen(
            ["python3", str(HOOK_PY), "cursor"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        for _ in range(20)
    ]
    for proc in procs:
        stdout, _stderr = proc.communicate(payload, timeout=10)
        assert proc.returncode == 0
        assert json.loads(stdout) == {"permission": "allow"}
    state = json.loads((telemetry_env["state"] / "conv-1.json").read_text())
    assert _series_value(state, "skill.reads") == 20


def test_shim_missing_python_exits_zero(tmp_path: Path) -> None:
    tools = tmp_path / "bin"
    tools.mkdir()
    for name in ("bash", "sh"):
        resolved = shutil.which(name)
        if resolved:
            dest = tools / name
            if not dest.exists():
                dest.symlink_to(resolved)
    env = {**os.environ, "PATH": str(tools), "HOOK_EVENT": "beforeReadFile"}
    result = subprocess.run(
        ["bash", str(HOOK_SH), "cursor"],
        input=b"{}",
        capture_output=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"permission": "allow"}


@pytest.mark.parametrize("fixture", sorted(FIXTURES.rglob("*.json")))
def test_fixtures_run_through_main(hook: Any, telemetry_env: dict[str, Path], fixture: Path) -> None:
    workspace = telemetry_env["ws"]
    raw = fixture.read_text().replace("__WS__", str(workspace))
    payload = json.loads(raw)
    mode = "claude" if fixture.parent.name == "claude" else "cursor"
    stdout = _run(hook, telemetry_env, payload, mode=mode)
    parsed = json.loads(stdout)
    assert isinstance(parsed, dict)
    event = payload.get("hook_event_name")
    if mode == "cursor" and event == "beforeReadFile":
        assert parsed == {"permission": "allow"}
    elif mode == "cursor" and event == "beforeSubmitPrompt":
        assert parsed == {"continue": True}
    else:
        assert parsed == {}
    if event in {"beforeReadFile", "PreToolUse"} and "foo" in json.dumps(payload):
        session = payload.get("conversation_id") or payload.get("session_id")
        state = _state(telemetry_env, session)
        assert _series_value(state, "skill.reads") >= 1


def test_session_id_with_slash_or_absolute_path_does_not_escape_state_dir(
    hook: Any, telemetry_env: dict[str, Path]
) -> None:
    root = telemetry_env["state"].parent
    victim = root / "escaped.json"
    victim.write_text("untouched")
    workspace = telemetry_env["ws"]
    bad_ids = (
        str(victim),
        "../escaped",
        "..",
        "foo/../bar",
        "foo/bar",
        "x" * (hook.SESSION_ID_MAX_LEN + 1),
    )
    for conversation_id in bad_ids:
        stdout = _run(hook, telemetry_env, _payload("sessionStart", workspace, conversation_id=conversation_id))
        assert json.loads(stdout) == {}
        assert victim.read_text() == "untouched"
        assert not (root / "escaped.lock").exists()
        assert not (root / "escaped.json.tmp").exists()
    state_dir = telemetry_env["state"]
    if state_dir.exists():
        names = {path.name for path in state_dir.iterdir() if path.suffix in {".json", ".lock"}}
        assert names == set()
    good = "bc-abc123"
    stdout = _run(hook, telemetry_env, _payload("sessionStart", workspace, conversation_id=good))
    assert json.loads(stdout) == {}
    written = state_dir / f"{good}.json"
    assert written.is_file()
    assert json.loads(written.read_text())["conversation_id"] == good


def test_state_dir_rejects_foreign_owned_tmp_and_uses_private_mode(
    hook: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = tmp_path / "private-state"
    monkeypatch.setenv("SKILL_TELEMETRY_STATE_DIR", str(private))
    chosen = hook._state_dir()
    assert chosen == private
    assert (private.stat().st_mode & 0o777) == 0o700
    session = private / "conv-1.json"
    hook._atomic_write(session, "{}")
    assert (session.stat().st_mode & 0o777) == 0o600

    hijack = tmp_path / "tmp" / "skill-telemetry"
    hijack.mkdir(parents=True)
    (hijack / "stolen.json").write_text("secret")
    monkeypatch.delenv("SKILL_TELEMETRY_STATE_DIR", raising=False)
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    fallback = hook._state_dir()
    assert fallback is not None
    assert fallback.resolve() != hijack.resolve()
    assert (hijack / "stolen.json").read_text() == "secret"
    assert list(hijack.glob("*.lock")) == []

    gc_dir = tmp_path / "gc"
    gc_dir.mkdir()
    ancient = time.time() - hook.TTL_S - 10
    stale_json = gc_dir / "old.json"
    stale_lock = gc_dir / "old.lock"
    other = gc_dir / "notes.txt"
    for path, body in ((stale_json, "{}"), (stale_lock, ""), (other, "keep")):
        path.write_text(body)
        os.utime(path, (ancient, ancient))
    hook._maybe_gc(gc_dir, time.time(), force=True)
    assert not stale_json.exists()
    assert not stale_lock.exists()
    assert other.read_text() == "keep"
