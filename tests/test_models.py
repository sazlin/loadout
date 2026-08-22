from pathlib import Path

import pytest

from loadout.errors import ValidationError
from loadout.models import CliTool, load_loadout, load_lockfile, load_manifest


def test_load_manifest_defaults(tmp_path: Path):
    p = tmp_path / ".loadout.yaml"
    p.write_text("source: https://github.com/sazlin/loadout\nref: v0.1.0\nloadouts:\n  - base\n")
    m = load_manifest(p)
    assert m.skills_dir == ".claude/skills"
    assert m.hooks_dir == ".cursor/hooks"
    assert m.agents_dir == ".claude/agents"
    assert m.claude_bridge is True
    assert m.include == []
    assert m.exclude == []


def test_load_manifest_rejects_malformed_yaml(tmp_path: Path):
    path = tmp_path / ".loadout.yaml"
    path.write_text("source: https://example.com/loadout\nloadouts: [\n")

    with pytest.raises(ValidationError, match=r"\.loadout\.yaml: invalid YAML"):
        load_manifest(path)


def test_load_lockfile_rejects_malformed_json(tmp_path: Path):
    path = tmp_path / ".loadout.lock"
    path.write_text('{"lockfile_version": 1,\n')

    with pytest.raises(ValidationError, match=r"\.loadout\.lock: invalid JSON"):
        load_lockfile(path)


def test_load_loadout_defaults_cli_tools_to_empty(tmp_path: Path) -> None:
    path = tmp_path / "base.yaml"
    path.write_text("name: base\ndescription: Base\n")

    loadout = load_loadout(path)

    assert loadout.cli_tools == []


def test_load_loadout_parses_named_cli_tools(tmp_path: Path) -> None:
    path = tmp_path / "python.yaml"
    path.write_text(
        "name: python\ndescription: Python\n"
        "cli_tools:\n"
        "  - name: jq\n"
        "    command: command -v jq >/dev/null || brew install jq\n"
        "  - name: gh\n"
        "    command: |\n"
        "      command -v gh >/dev/null || brew install gh\n"
    )

    loadout = load_loadout(path)

    assert loadout.cli_tools == [
        CliTool(name="jq", command="command -v jq >/dev/null || brew install jq"),
        CliTool(name="gh", command="command -v gh >/dev/null || brew install gh"),
    ]


def test_load_loadout_rejects_unknown_cli_tools_key(tmp_path: Path) -> None:
    path = tmp_path / "base.yaml"
    path.write_text("name: base\ndescription: Base\ncli_tools: []\nunknown: true\n")

    with pytest.raises(ValidationError, match="unknown key"):
        load_loadout(path)


def test_load_loadout_rejects_cli_tools_that_are_not_a_list(tmp_path: Path) -> None:
    path = tmp_path / "base.yaml"
    path.write_text("name: base\ndescription: Base\ncli_tools: brew install jq\n")

    with pytest.raises(ValidationError, match="cli_tools must be a list"):
        load_loadout(path)


def test_load_loadout_rejects_cli_tool_that_is_not_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "base.yaml"
    path.write_text("name: base\ndescription: Base\ncli_tools:\n  - brew install jq\n")

    with pytest.raises(ValidationError, match=r"cli_tools\[0\] must be a mapping"):
        load_loadout(path)


def test_load_loadout_rejects_cli_tool_missing_name(tmp_path: Path) -> None:
    path = tmp_path / "base.yaml"
    path.write_text("name: base\ndescription: Base\ncli_tools:\n  - command: true\n")

    with pytest.raises(ValidationError, match=r"cli_tools\[0\] requires non-empty name"):
        load_loadout(path)


def test_load_loadout_rejects_cli_tool_missing_command(tmp_path: Path) -> None:
    path = tmp_path / "base.yaml"
    path.write_text("name: base\ndescription: Base\ncli_tools:\n  - name: jq\n")

    with pytest.raises(ValidationError, match=r"cli_tools\[0\] requires non-empty command"):
        load_loadout(path)


def test_load_loadout_rejects_yaml_boolean_cli_tool_command(tmp_path: Path) -> None:
    path = tmp_path / "base.yaml"
    path.write_text("name: base\ndescription: Base\ncli_tools:\n  - name: jq\n    command: true\n")

    with pytest.raises(ValidationError, match=r"cli_tools\[0\] requires non-empty command"):
        load_loadout(path)


def test_load_loadout_rejects_blank_cli_tool_fields(tmp_path: Path) -> None:
    path = tmp_path / "base.yaml"
    path.write_text("name: base\ndescription: Base\ncli_tools:\n  - name: '  '\n    command: '  '\n")

    with pytest.raises(ValidationError, match=r"cli_tools\[0\] requires non-empty name"):
        load_loadout(path)


def test_load_loadout_rejects_unknown_cli_tool_entry_keys(tmp_path: Path) -> None:
    path = tmp_path / "base.yaml"
    path.write_text(
        "name: base\ndescription: Base\ncli_tools:\n  - name: jq\n    command: 'true'\n    optional: true\n"
    )

    with pytest.raises(ValidationError, match=r"cli_tools\[0\] has unknown key"):
        load_loadout(path)


def test_load_loadout_rejects_duplicate_cli_tool_names_in_one_loadout(tmp_path: Path) -> None:
    path = tmp_path / "base.yaml"
    path.write_text(
        "name: base\ndescription: Base\n"
        "cli_tools:\n"
        "  - name: jq\n"
        "    command: 'true'\n"
        "  - name: jq\n"
        "    command: 'true'\n"
    )

    with pytest.raises(ValidationError, match="duplicate cli_tools name"):
        load_loadout(path)
