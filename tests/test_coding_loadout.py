"""Contracts for the coding loadout and vendored ponytail artifacts."""

from __future__ import annotations

import hashlib
import json
import os
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
)
SKILL_SRCS = tuple(f"skills/{name}" for name in SKILL_NAMES)
RULE_SRC = "rules/coding/ponytail.mdc"
HOOK_SRC = "hooks/ponytail-activate"
HOOK_SCRIPT = REPO / "hooks" / "ponytail-activate" / "ponytail-activate"
UPSTREAM = "https://github.com/DietrichGebert/ponytail"
PONYTAIL_COMMIT = "974d940a1c5344210874150b98ff0d2c861fab6a"


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def test_coding_loadout_ships_ponytail_artifacts() -> None:
    loadout = load_loadout(REPO / "loadouts" / "coding.yaml")
    assert loadout.name == "coding"
    assert loadout.extends == []
    assert {entry["src"] for entry in loadout.skills} == set(SKILL_SRCS)
    assert {entry["src"] for entry in loadout.rules} == {RULE_SRC}
    assert {entry["src"] for entry in loadout.hooks} == {HOOK_SRC}
    assert loadout.agents == []
    assert loadout.mcps == []
    assert loadout.cli_tools == []


def test_ponytail_skills_parse_and_drop_plugin_only_frontmatter() -> None:
    for name, src in zip(SKILL_NAMES, SKILL_SRCS, strict=True):
        skill_md = REPO / src / "SKILL.md"
        text = skill_md.read_text()
        parse_skill_md(skill_md, text, dir_name=name)
        data = yaml.safe_load(text.split("---", 2)[1])
        assert "argument-hint" not in data
        assert "<" not in data["description"]
        assert ">" not in data["description"]


def test_ponytail_skill_evals_are_colocated() -> None:
    for name, src in zip(SKILL_NAMES, SKILL_SRCS, strict=True):
        evals = REPO / src / "evals" / "evals.json"
        payload = json.loads(evals.read_text())
        assert payload["skill_name"] == name
        assert payload["evals"]
        for index, entry in enumerate(payload["evals"]):
            for relative in entry.get("files", []):
                path = REPO / src / relative
                assert path.is_file(), f"{name} evals[{index}] missing {relative}"


def test_ponytail_skill_source_pins_exist() -> None:
    for src in SKILL_SRCS:
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


def test_coding_sync_vendors_ponytail_without_evals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
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

    cursor = json.loads((project / ".cursor/hooks.json").read_text())
    assert cursor["hooks"]["sessionStart"] == [{"command": ".cursor/hooks/ponytail-activate/ponytail-activate cursor"}]
    claude = json.loads((project / ".claude/settings.json").read_text())
    assert claude["hooks"]["SessionStart"] == [
        {
            "matcher": "startup|resume|clear|compact",
            "hooks": [
                {
                    "type": "command",
                    "command": ("${CLAUDE_PROJECT_DIR}/.cursor/hooks/ponytail-activate/ponytail-activate"),
                }
            ],
        }
    ]


def _run_ponytail_activate(project: Path, *args: str, env: dict[str, str] | None = None) -> dict:
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
