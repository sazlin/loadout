"""Contracts for the coding loadout and vendored ponytail / RTK artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from loadout.frontmatter import parse_rule, parse_skill_md
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
SKILL_NAMES = (
    "ponytail",
    "ponytail-review",
    "ponytail-audit",
    "ponytail-debt",
    "ponytail-gain",
    "ponytail-help",
    "rtk",
)
SKILL_SRCS = tuple(f"skills/{name}" for name in SKILL_NAMES)
PONYTAIL_SKILL_NAMES = SKILL_NAMES[:-1]
PONYTAIL_SKILL_SRCS = SKILL_SRCS[:-1]
RULE_SRC = "rules/coding/ponytail.mdc"
PONYTAIL_HOOK_SRC = "hooks/ponytail-activate"
RTK_HOOK_SRC = "hooks/rtk-rewrite"
HOOK_SRCS = (PONYTAIL_HOOK_SRC, RTK_HOOK_SRC)
HOOK_SCRIPT = REPO / "hooks" / "ponytail-activate" / "ponytail-activate"
RTK_HOOK_SCRIPT = REPO / "hooks" / "rtk-rewrite" / "rtk-rewrite.sh"
UPSTREAM = "https://github.com/DietrichGebert/ponytail"
PONYTAIL_COMMIT = "974d940a1c5344210874150b98ff0d2c861fab6a"
RTK_UPSTREAM = "https://github.com/rtk-ai/rtk"
RTK_VERSION = "0.48.0"
RTK_COMMIT = "fde0a8f185945556f51718de0f4c430bb62b3df6"
RTK_MUSL_SHA256 = "e4e650fa1677c0de2f6839a6040d7b17f312d32f163c402b75af70e9e5af1a91"
CURL_PIPE_SH = re.compile(r"curl[^\n]*\|\s*(?:ba)?sh")
CARGO_INSTALL_CRATES_RTK = re.compile(r"cargo\s+install(?:\s+--locked)?\s+rtk\b")


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def _silence_cli_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("loadout.sync.run_cli_tools", lambda tools, project_root: None)


def test_coding_loadout_ships_ponytail_and_rtk_artifacts() -> None:
    loadout = load_loadout(REPO / "loadouts" / "coding.yaml")
    assert loadout.name == "coding"
    assert loadout.extends == []
    assert {entry["src"] for entry in loadout.skills} == set(SKILL_SRCS)
    assert {entry["src"] for entry in loadout.rules} == {RULE_SRC}
    assert {entry["src"] for entry in loadout.hooks} == set(HOOK_SRCS)
    assert loadout.agents == []
    assert loadout.mcps == []
    assert len(loadout.cli_tools) == 1
    tool = loadout.cli_tools[0]
    assert tool.name == "rtk"
    assert RTK_VERSION in tool.command
    assert "rtk-ai/rtk" in tool.command
    assert "rtk gain" in tool.command
    assert RTK_MUSL_SHA256 in tool.command
    assert "curl" in tool.command
    assert "| sh" not in tool.command
    assert "|sh" not in tool.command.replace(" ", "")
    assert CARGO_INSTALL_CRATES_RTK.search(tool.command) is None
    assert "crates.io" not in tool.command


def test_ponytail_skills_parse_and_drop_plugin_only_frontmatter() -> None:
    for name, src in zip(PONYTAIL_SKILL_NAMES, PONYTAIL_SKILL_SRCS, strict=True):
        skill_md = REPO / src / "SKILL.md"
        text = skill_md.read_text()
        parse_skill_md(skill_md, text, dir_name=name)
        data = yaml.safe_load(text.split("---", 2)[1])
        assert "argument-hint" not in data
        assert "<" not in data["description"]
        assert ">" not in data["description"]


def test_ponytail_skill_evals_are_colocated() -> None:
    for name, src in zip(PONYTAIL_SKILL_NAMES, PONYTAIL_SKILL_SRCS, strict=True):
        evals = REPO / src / "evals" / "evals.json"
        payload = json.loads(evals.read_text())
        assert payload["skill_name"] == name
        assert payload["evals"]
        for index, entry in enumerate(payload["evals"]):
            for relative in entry.get("files", []):
                path = REPO / src / relative
                assert path.is_file(), f"{name} evals[{index}] missing {relative}"


def test_ponytail_skill_source_pins_exist() -> None:
    for src in PONYTAIL_SKILL_SRCS:
        source = REPO / src / "SOURCE.md"
        text = source.read_text()
        assert UPSTREAM in text
        assert PONYTAIL_COMMIT in text
        assert "evals/" in text
        digest = hashlib.sha256((REPO / src / "SKILL.md").read_bytes()).hexdigest()
        assert digest in text


def test_ponytail_help_does_not_send_agents_to_plugin_marketplace() -> None:
    text = (REPO / "skills" / "ponytail-help" / "SKILL.md").read_text()
    assert "/plugin marketplace" not in text
    assert "loadout sync" in text


def test_ponytail_rule_is_globbed_not_always_apply() -> None:
    path = REPO / RULE_SRC
    meta = parse_rule(path, path.read_text())
    assert meta.always_apply is False
    assert meta.globs
    assert "YAGNI" in path.read_text() or "yagni" in path.read_text().lower()


# Each tuple is (rule substring, skill substring) for one ladder rung.
_CORE_LADDER_RUNGS = (
    ("Does this need to be built", "Does this need to exist"),
    ("already exist in this codebase", "Already in this codebase"),
    ("standard library", "Stdlib"),
    ("native platform feature", "Native platform feature"),
    ("already-installed dependency", "Already-installed dependency"),
    ("one line", "one line"),
    ("minimum code", "minimum code"),
)


def test_ponytail_rule_core_ladder_matches_skill() -> None:
    rule_text = (REPO / RULE_SRC).read_text()
    skill_text = (REPO / "skills" / "ponytail" / "SKILL.md").read_text()
    assert "skills/ponytail/SKILL.md" in rule_text
    rule_lower = rule_text.lower()
    skill_lower = skill_text.lower()
    for rule_marker, skill_marker in _CORE_LADDER_RUNGS:
        assert rule_marker.lower() in rule_lower, f"rule missing ladder rung: {rule_marker!r}"
        assert skill_marker.lower() in skill_lower, f"skill missing ladder rung: {skill_marker!r}"


def test_ponytail_activate_hook_matcher_is_startup_only() -> None:
    hook_yaml = REPO / PONYTAIL_HOOK_SRC / "hook.yaml"
    data = yaml.safe_load(hook_yaml.read_text())
    matcher = data["claude"]["matcher"]
    assert matcher == "startup"
    assert "compact" not in matcher
    assert "resume" not in matcher


def test_coding_sync_vendors_ponytail_without_evals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    _silence_cli_tools(monkeypatch)
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [coding]
""",
    )
    sync(project)

    for name in SKILL_NAMES:
        dest = project / ".claude/skills" / name / "SKILL.md"
        assert dest.is_file()
        assert not (project / ".claude/skills" / name / "evals").exists()

    assert (project / ".cursor/rules/ponytail.mdc").is_file()
    script = project / ".cursor/hooks/ponytail-activate/ponytail-activate"
    assert script.is_file()
    assert os.access(script, os.X_OK)
    assert not (project / ".cursor/hooks/ponytail-activate/hook.yaml").exists()
    rtk_script = project / ".cursor/hooks/rtk-rewrite/rtk-rewrite.sh"
    assert rtk_script.is_file()
    assert os.access(rtk_script, os.X_OK)
    assert not (project / ".cursor/hooks/rtk-rewrite/hook.yaml").exists()

    cursor = json.loads((project / ".cursor/hooks.json").read_text())
    assert cursor["hooks"]["sessionStart"] == [{"command": ".cursor/hooks/ponytail-activate/ponytail-activate cursor"}]
    assert cursor["hooks"]["beforeShellExecution"] == [{"command": ".cursor/hooks/rtk-rewrite/rtk-rewrite.sh cursor"}]
    claude = json.loads((project / ".claude/settings.json").read_text())
    assert claude["hooks"]["SessionStart"] == [
        {
            "matcher": "startup",
            "hooks": [
                {
                    "type": "command",
                    "command": ("${CLAUDE_PROJECT_DIR}/.cursor/hooks/ponytail-activate/ponytail-activate"),
                }
            ],
        }
    ]
    assert claude["hooks"]["PreToolUse"] == [
        {
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": ("${CLAUDE_PROJECT_DIR}/.cursor/hooks/rtk-rewrite/rtk-rewrite.sh"),
                }
            ],
        }
    ]


def _run_ponytail_activate(
    project: Path, *args: str, env: dict[str, str] | None = None
) -> dict[str, object]:
    """Run the synced hook as if installed under project/.cursor/hooks/ponytail-activate/."""
    hook_dir = project / ".cursor" / "hooks" / "ponytail-activate"
    hook_dir.mkdir(parents=True)
    script = hook_dir / "ponytail-activate"
    script.write_bytes(HOOK_SCRIPT.read_bytes())
    script.chmod(0o755)
    result = subprocess.run(
        [str(script), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    return json.loads(result.stdout)


def test_ponytail_activate_cursor_payload_includes_skill(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: ponytail\ndescription: test\n---\n\n# Ladder marker XYZ\n")

    payload = _run_ponytail_activate(project, "cursor")

    assert "additional_context" in payload
    assert "hookSpecificOutput" not in payload
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "Ladder marker XYZ" in context
    assert "PONYTAIL" in context.upper() or "ponytail" in context.lower()


def test_ponytail_activate_claude_payload_shape(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: ponytail\ndescription: test\n---\n\n# Claude marker ABC\n")

    payload = _run_ponytail_activate(project)

    assert "additional_context" not in payload
    hook_out = payload["hookSpecificOutput"]
    assert isinstance(hook_out, dict)
    assert hook_out["hookEventName"] == "SessionStart"
    assert "Claude marker ABC" in hook_out["additionalContext"]


def test_ponytail_activate_off_mode_skips_skill_body(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: ponytail\ndescription: test\n---\n\n# Should stay out\n")

    payload = _run_ponytail_activate(project, "cursor", env={"PONYTAIL_DEFAULT_MODE": "off"})
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "Should stay out" not in context


def test_ponytail_activate_missing_skill_emits_error_and_exits_zero(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()

    payload = _run_ponytail_activate(project, "cursor")
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "Error: ponytail skill not found" in context
    assert ".claude/skills/ponytail/SKILL.md" in context
    assert "/home/" not in context
    assert not context.startswith("/")


def test_ponytail_activate_json_safe_control_characters(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_bytes(
        b"---\nname: ponytail\ndescription: test\n---\n\n"
        b"Control chars: \x00 NUL \x0c form-feed \x1f unit-sep\n"
    )

    payload = _run_ponytail_activate(project, "cursor")
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "Control chars:" in context
    assert "\x0c" in context
    assert "\x1f" in context


def test_ponytail_activate_invalid_env_mode_falls_back_to_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: ponytail\ndescription: test\n---\n\n# Invalid env fallback marker\n"
    )

    config_dir = tmp_path / "config" / "ponytail"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text('{"defaultMode": "off"}')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    payload = _run_ponytail_activate(
        project, "cursor", env={"PONYTAIL_DEFAULT_MODE": "banana"}
    )
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "Invalid env fallback marker" in context


def test_ponytail_activate_respects_config_file_default_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: ponytail\ndescription: test\n---\n\n# Config mode marker\n")

    config_dir = tmp_path / "config" / "ponytail"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text('{"defaultMode": "off"}')
    monkeypatch.delenv("PONYTAIL_DEFAULT_MODE", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    payload = _run_ponytail_activate(project, "cursor")
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "Config mode marker" not in context


def test_ponytail_activate_lite_mode_filters_non_lite_examples(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: ponytail\ndescription: test\n---\n\n"
        "## Intensity\n\n"
        "| Level | What change |\n"
        "|-------|-------------|\n"
        "| **lite** | Lite row kept. |\n"
        "| **full** | Full row dropped. |\n"
        "| **ultra** | Ultra row dropped. |\n\n"
        'Example: "Add a cache."\n'
        '- lite: "Lite example kept."\n'
        '- full: "Full example dropped."\n'
        '- ultra: "Ultra example dropped."\n'
    )

    payload = _run_ponytail_activate(project, "cursor", env={"PONYTAIL_DEFAULT_MODE": "lite"})
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "name: ponytail" not in context
    assert "Lite row kept." in context
    assert "Full row dropped." not in context
    assert "Ultra row dropped." not in context
    assert "Lite example kept." in context
    assert "Full example dropped." not in context
    assert "Ultra example dropped." not in context


def test_ponytail_activate_rejects_symlink_skill_path(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill_dir = project / ".claude" / "skills" / "ponytail"
    skill_dir.mkdir(parents=True)
    secret = project / ".env"
    secret.write_text("SECRET_API_KEY=super-secret-value\n")
    skill_link = skill_dir / "SKILL.md"
    skill_link.symlink_to(secret)

    payload = _run_ponytail_activate(project, "cursor")
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "SECRET_API_KEY" not in context
    assert "super-secret-value" not in context
    assert "symlink" in context.lower()


def test_ponytail_activate_frontmatter_only_skill_emits_empty_body(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: ponytail\ndescription: test\n---\n")

    payload = _run_ponytail_activate(project, "cursor")
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "PONYTAIL MODE ACTIVE" in context
    assert "unable to read" not in context.lower()
    assert "name: ponytail" not in context


def test_ponytail_activate_rejects_oversized_skill(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    oversized_body = "X" * 100_000
    skill.write_text(f"---\nname: ponytail\ndescription: test\n---\n\n{oversized_body}\n")

    hook_dir = project / ".cursor" / "hooks" / "ponytail-activate"
    hook_dir.mkdir(parents=True)
    script = hook_dir / "ponytail-activate"
    script.write_bytes(HOOK_SCRIPT.read_bytes())
    script.chmod(0o755)
    result = subprocess.run(
        [str(script), "cursor"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ},
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert oversized_body not in context
    assert "65536" in context or "byte limit" in context.lower()
    assert len(context) < 10_000


def test_ponytail_activate_unreadable_skill_exits_zero(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: ponytail\ndescription: test\n---\n\n# Unreadable marker\n")
    skill.chmod(0o000)

    hook_dir = project / ".cursor" / "hooks" / "ponytail-activate"
    hook_dir.mkdir(parents=True)
    script = hook_dir / "ponytail-activate"
    script.write_bytes(HOOK_SCRIPT.read_bytes())
    script.chmod(0o755)
    result = subprocess.run(
        [str(script), "cursor"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ},
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "Unreadable marker" not in context
    assert "unable to read" in context.lower() or "error" in context.lower()


def test_ponytail_activate_finds_skill_when_skills_dir_relocated(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill = project / ".agents" / "skills" / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: ponytail\ndescription: test\n---\n\n# Relocated marker\n")
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [coding]
skills_dir: .agents/skills
""",
    )

    payload = _run_ponytail_activate(project, "cursor")
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "Relocated marker" in context
    assert "Error: ponytail skill not found" not in context


def test_rtk_skill_parses_and_has_colocated_evals() -> None:
    skill_md = REPO / "skills" / "rtk" / "SKILL.md"
    text = skill_md.read_text()
    parse_skill_md(skill_md, text, dir_name="rtk")
    data = yaml.safe_load(text.split("---", 2)[1])
    assert "<" not in data["description"]
    assert ">" not in data["description"]
    evals = json.loads((REPO / "skills" / "rtk" / "evals" / "evals.json").read_text())
    assert evals["skill_name"] == "rtk"
    assert evals["evals"]


def test_rtk_skill_source_pins_token_killer_release() -> None:
    source = (REPO / "skills" / "rtk" / "SOURCE.md").read_text()
    assert RTK_UPSTREAM in source
    assert RTK_COMMIT in source
    assert RTK_VERSION in source
    digest = hashlib.sha256((REPO / "skills" / "rtk" / "SKILL.md").read_bytes()).hexdigest()
    assert digest in source


def test_rtk_skill_does_not_instruct_unpinned_or_wrong_installs() -> None:
    text = (REPO / "skills" / "rtk" / "SKILL.md").read_text()
    assert CURL_PIPE_SH.search(text) is None
    assert CARGO_INSTALL_CRATES_RTK.search(text) is None
    assert "rtk gain" in text
    assert "rtk init" in text
    assert "Do not" in text or "do not" in text
    lowered = text.lower()
    assert "crates.io" in lowered
    assert "loadout" in lowered


def test_rtk_hook_source_pins_exist() -> None:
    source = (REPO / "hooks" / "rtk-rewrite" / "SOURCE.md").read_text()
    assert RTK_UPSTREAM in source
    assert RTK_COMMIT in source
    assert "rtk hook cursor" in source
    assert "rtk hook claude" in source
    assert "rtk init" in source


def _install_rtk_hook(project: Path) -> Path:
    hook_dir = project / ".cursor" / "hooks" / "rtk-rewrite"
    hook_dir.mkdir(parents=True)
    script = hook_dir / "rtk-rewrite.sh"
    script.write_bytes(RTK_HOOK_SCRIPT.read_bytes())
    script.chmod(0o755)
    return script


def _run_rtk_hook(script: Path, stdin: str, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(script), *args],
        input=stdin,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _path_without_rtk() -> str:
    parts = []
    for entry in os.environ.get("PATH", "").split(":"):
        if not entry:
            continue
        if (Path(entry) / "rtk").exists():
            continue
        parts.append(entry)
    return ":".join(parts)


def _write_fake_rtk(bin_dir: Path) -> None:
    script = bin_dir / "rtk"
    script.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "gain" ]]; then
  exit 0
fi
if [[ "${1:-}" == "hook" && "${2:-}" == "cursor" ]]; then
  cmd="$(jq -r '.tool_input.command // empty')"
  if [[ "$cmd" == "git status" ]]; then
    jq -n '{continue:true, permission:"allow", updated_input:{command:"rtk git status"}}'
    exit 0
  fi
  printf '{}\\n'
  exit 0
fi
if [[ "${1:-}" == "hook" && "${2:-}" == "claude" ]]; then
  cmd="$(jq -r '.tool_input.command // empty')"
  if [[ "$cmd" == "pytest -q" ]]; then
    jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse", permissionDecision:"allow", updatedInput:{command:"rtk pytest -q"}}}'
    exit 0
  fi
  printf '{}\\n'
  exit 0
fi
exit 1
"""
    )
    script.chmod(0o755)


def test_rtk_rewrite_fail_open_when_rtk_missing(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    script = _install_rtk_hook(project)
    env = {**os.environ, "PATH": _path_without_rtk()}
    result = _run_rtk_hook(script, '{"command":"git status"}', "cursor", env=env)
    payload = json.loads(result.stdout)
    assert payload == {"permission": "allow"}


def test_rtk_rewrite_remaps_cursor_command_for_rtk_hook(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    script = _install_rtk_hook(project)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_rtk(bin_dir)
    env = {**os.environ, "PATH": f"{bin_dir}:{_path_without_rtk()}"}
    result = _run_rtk_hook(script, '{"command":"git status"}', "cursor", env=env)
    payload = json.loads(result.stdout)
    assert payload["permission"] == "allow"
    assert payload["updated_input"]["command"] == "rtk git status"


def test_rtk_rewrite_delegates_claude_payload(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    script = _install_rtk_hook(project)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_rtk(bin_dir)
    env = {**os.environ, "PATH": f"{bin_dir}:{_path_without_rtk()}"}
    stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": "pytest -q"}})
    result = _run_rtk_hook(script, stdin, env=env)
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["updatedInput"]["command"] == "rtk pytest -q"


def test_ponytail_activate_works_without_realpath_binary(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skill = project / ".claude" / "skills" / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: ponytail\ndescription: test\n---\n\n# No realpath marker\n")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_realpath = fake_bin / "realpath"
    fake_realpath.write_text("#!/bin/sh\nexit 1\n")
    fake_realpath.chmod(0o755)

    payload = _run_ponytail_activate(
        project,
        "cursor",
        env={"PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"},
    )
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "No realpath marker" in context
    assert "Error: ponytail skill not found" not in context


def test_ponytail_activate_finds_skill_with_absolute_skills_dir(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    skills_root = tmp_path / "test-skills"
    skill = skills_root / "ponytail" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: ponytail\ndescription: test\n---\n\n# Absolute marker\n")
    write_manifest(
        project,
        f"""source: https://github.com/sazlin/loadout
ref: main
loadouts: [coding]
skills_dir: {skills_root}
""",
    )

    payload = _run_ponytail_activate(project, "cursor")
    context = payload["additional_context"]
    assert isinstance(context, str)
    assert "Absolute marker" in context
    assert "Error: ponytail skill not found" not in context
