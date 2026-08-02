from pathlib import Path

import pytest

from loadout.errors import ValidationError
from loadout.models import Manifest
from loadout.resolve import ResolvedFile, resolve


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "mini_loadout"


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
