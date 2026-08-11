import shutil
from pathlib import Path

import pytest

from loadout.errors import ValidationError
from loadout.models import Manifest
from loadout.resolve import ResolvedFile, resolve

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "mini_loadout"


def copy_fixture(tmp_path: Path) -> Path:
    source = tmp_path / "loadout_src"
    shutil.copytree(FIXTURE_ROOT, source)
    return source


def manifest(
    *,
    loadouts: list[str] | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> Manifest:
    return Manifest(
        source="https://example.test/loadout",
        ref="test",
        loadouts=loadouts or ["python"],
        include=include or [],
        exclude=exclude or [],
    )


def file_set(files: list[ResolvedFile]) -> set[tuple[str, str, str]]:
    return {(file.src, file.dest, file.kind) for file in files}


def test_resolve_expands_extended_loadouts_and_skips_skill_root_evals():
    files = resolve(manifest(), FIXTURE_ROOT)

    assert file_set(files) == {
        ("rules/core/a.mdc", ".cursor/rules/a.mdc", "rule"),
        ("rules/python/b.mdc", ".cursor/rules/b.mdc", "rule"),
        ("skills/demo/SKILL.md", ".claude/skills/demo/SKILL.md", "skill_file"),
        (
            "skills/demo/scripts/run.sh",
            ".claude/skills/demo/scripts/run.sh",
            "skill_file",
        ),
        (
            "skills/demo/references/runbook.md",
            ".claude/skills/demo/references/runbook.md",
            "skill_file",
        ),
        (
            "skills/demo/assets/template.txt",
            ".claude/skills/demo/assets/template.txt",
            "skill_file",
        ),
        (
            "skills/demo/agents/reviewer.md",
            ".claude/skills/demo/agents/reviewer.md",
            "skill_file",
        ),
        (
            "hooks/demo/guard.sh",
            ".cursor/hooks/demo/guard.sh",
            "hook_file",
        ),
        (
            "agents/demo_agent.md",
            ".claude/agents/demo_agent.md",
            "agent",
        ),
        (
            "mcps/demo-docs/mcp.yaml",
            "__mcp__/demo-docs",
            "mcp",
        ),
    }


def test_resolve_include_uses_default_destination():
    files = resolve(manifest(loadouts=["base"], include=["rules/python/b.mdc"]), FIXTURE_ROOT)

    assert ("rules/python/b.mdc", ".cursor/rules/b.mdc", "rule") in file_set(files)


def test_resolve_exclude_removes_expanded_skill_files():
    files = resolve(manifest(exclude=["skills/demo"]), FIXTURE_ROOT)

    assert all(not file.src.startswith("skills/demo/") for file in files)


def test_resolve_rejects_unmatched_exclude():
    with pytest.raises(ValidationError, match="rules/missing.mdc"):
        resolve(manifest(exclude=["rules/missing.mdc"]), FIXTURE_ROOT)


def test_resolve_rejects_unmatched_include():
    with pytest.raises(ValidationError, match="rules/missing.mdc"):
        resolve(manifest(include=["rules/missing.mdc"]), FIXTURE_ROOT)


def test_resolve_rejects_a_loadout_referencing_a_missing_skill_directory(tmp_path: Path):
    source = copy_fixture(tmp_path)
    (source / "loadouts" / "base.yaml").write_text(
        "name: base\ndescription: Base rules and skills\nskills:\n  - src: skills/gone\n"
    )

    with pytest.raises(ValidationError, match="skills/gone"):
        resolve(manifest(loadouts=["base"]), source)


def test_resolve_rejects_a_skill_src_that_is_a_file(tmp_path: Path):
    source = copy_fixture(tmp_path)
    (source / "loadouts" / "base.yaml").write_text(
        "name: base\ndescription: Base rules and skills\nskills:\n  - src: skills/demo/SKILL.md\n"
    )

    with pytest.raises(ValidationError, match="skills/demo/SKILL.md"):
        resolve(manifest(loadouts=["base"]), source)


def test_resolve_rejects_extends_cycles(tmp_path: Path):
    source = copy_fixture(tmp_path)
    (source / "loadouts" / "base.yaml").write_text(
        "name: base\nextends: [python]\ndescription: Base\nrules:\n  - src: rules/core/a.mdc\n"
    )
    (source / "loadouts" / "python.yaml").write_text(
        "name: python\nextends: [base]\ndescription: Python\nrules:\n  - src: rules/python/b.mdc\n"
    )

    with pytest.raises(ValidationError, match="cycle"):
        resolve(manifest(loadouts=["python"]), source)


def test_resolve_rejects_a_loadout_that_extends_itself(tmp_path: Path):
    source = copy_fixture(tmp_path)
    (source / "loadouts" / "base.yaml").write_text(
        "name: base\nextends: [base]\ndescription: Base\nrules:\n  - src: rules/core/a.mdc\n"
    )

    with pytest.raises(ValidationError, match="cycle"):
        resolve(manifest(loadouts=["base"]), source)


def test_resolve_reports_malformed_loadout_yaml_as_a_validation_error(tmp_path: Path):
    source = copy_fixture(tmp_path)
    (source / "loadouts" / "base.yaml").write_text("name: base\nextends: [\n")

    with pytest.raises(ValidationError, match="invalid YAML"):
        resolve(manifest(loadouts=["base"]), source)
