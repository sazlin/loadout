from __future__ import annotations

import json
from pathlib import Path

from loadout.lint import lint_repo

FIXTURE = Path(__file__).parent / "fixtures" / "mini_loadout"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def base_repo(root: Path) -> None:
    write(
        root / "rules" / "core" / "a.mdc",
        "---\ndescription: Core rule\n---\n\nCore rule.\n",
    )
    write(
        root / "skills" / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: Demo skill\n---\n\n# Demo\n",
    )
    write(
        root / "loadouts" / "base.yaml",
        "name: base\ndescription: Base rules and skills\n"
        "rules:\n  - src: rules/core/a.mdc\n"
        "skills:\n  - src: skills/demo\n",
    )


def test_clean_fixture_repo_lints_with_no_errors_or_warnings() -> None:
    result = lint_repo(FIXTURE)

    assert result.ok
    assert result.errors == []
    assert result.warnings == []


def test_repo_with_no_content_directories_lints_cleanly(tmp_path: Path) -> None:
    result = lint_repo(tmp_path)

    assert result.ok
    assert result.errors == []
    assert result.warnings == []


def test_underscore_prefixed_agent_markdown_is_not_linted_or_an_orphan(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(
        tmp_path / "agents" / "_agent_template.md",
        "# Template\n\nNot an agent. Missing frontmatter on purpose.\n",
    )

    result = lint_repo(tmp_path)

    assert result.ok
    assert result.errors == []


def test_orphan_rule_not_referenced_by_any_loadout_is_an_error(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(
        tmp_path / "rules" / "python" / "orphan.mdc",
        "---\ndescription: Unused rule\n---\n\nUnused.\n",
    )

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("rules/python/orphan.mdc" in error and "orphan" in error for error in result.errors)


def test_orphan_skill_not_referenced_by_any_loadout_is_an_error(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(
        tmp_path / "skills" / "unused" / "SKILL.md",
        "---\nname: unused\ndescription: Unused skill\n---\n\n# Unused\n",
    )

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("skills/unused" in error and "orphan" in error for error in result.errors)


def test_rule_missing_description_is_an_error(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(tmp_path / "rules" / "core" / "a.mdc", "---\nalwaysApply: true\n---\n\nCore.\n")

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("description" in error for error in result.errors)


def test_always_apply_outside_rules_core_is_an_error(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(
        tmp_path / "rules" / "python" / "always.mdc",
        "---\ndescription: Should not always apply\nalwaysApply: true\n---\n\nBody.\n",
    )
    write(
        tmp_path / "loadouts" / "python.yaml",
        "name: python\ndescription: Python rules\nrules:\n  - src: rules/python/always.mdc\n",
    )

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("rules/python/always.mdc" in error and "alwaysApply" in error for error in result.errors)


def test_skill_missing_skill_md_is_an_error(tmp_path: Path) -> None:
    base_repo(tmp_path)
    (tmp_path / "skills" / "broken").mkdir(parents=True)
    write(
        tmp_path / "loadouts" / "python.yaml",
        "name: python\ndescription: Python rules\nskills:\n  - src: skills/broken\n",
    )

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("skills/broken" in error and "missing SKILL.md" in error for error in result.errors)


def test_loadout_referencing_a_missing_skill_directory_is_an_error(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(
        tmp_path / "loadouts" / "python.yaml",
        "name: python\ndescription: Python rules\nskills:\n  - src: skills/gone\n",
    )

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("skills/gone" in error for error in result.errors)


def test_skill_name_directory_mismatch_is_an_error(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(
        tmp_path / "skills" / "demo" / "SKILL.md",
        "---\nname: not-demo\ndescription: Demo skill\n---\n\n# Demo\n",
    )

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("directory name" in error for error in result.errors)


def test_stray_nested_skill_md_below_skill_root_is_an_error(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(
        tmp_path / "skills" / "demo" / "references" / "nested" / "SKILL.md",
        "---\nname: nested\ndescription: Should not exist here\n---\n\n# Nested\n",
    )

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("skills/demo/references/nested/SKILL.md" in error and "stray" in error for error in result.errors)


def test_eval_file_referencing_missing_path_is_an_error(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(
        tmp_path / "skills" / "demo" / "evals" / "evals.json",
        json.dumps(
            {
                "skill_name": "demo",
                "evals": [{"id": 1, "files": ["evals/files/missing.sql"]}],
            }
        ),
    )

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("evals/files/missing.sql" in error for error in result.errors)


def test_eval_file_referencing_existing_path_is_fine(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(tmp_path / "skills" / "demo" / "evals" / "files" / "schema.sql", "select 1;\n")
    write(
        tmp_path / "skills" / "demo" / "evals" / "evals.json",
        json.dumps(
            {
                "skill_name": "demo",
                "evals": [{"id": 1, "files": ["evals/files/schema.sql"]}],
            }
        ),
    )

    result = lint_repo(tmp_path)

    assert result.ok


def test_loadout_extends_cycle_is_an_error(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(
        tmp_path / "loadouts" / "base.yaml",
        "name: base\nextends: [python]\ndescription: Base\nrules:\n  - src: rules/core/a.mdc\n",
    )
    write(
        tmp_path / "loadouts" / "python.yaml",
        "name: python\nextends: [base]\ndescription: Python\nskills:\n  - src: skills/demo\n",
    )

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("cycle" in error for error in result.errors)


def test_loadout_extends_missing_parent_is_an_error(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(
        tmp_path / "loadouts" / "child.yaml",
        "name: child\nextends: [missing]\ndescription: Child\n",
    )

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("Loadout not found: missing" in error for error in result.errors)


def test_loadout_malformed_yaml_is_an_error(tmp_path: Path) -> None:
    base_repo(tmp_path)
    write(tmp_path / "loadouts" / "bad.yaml", "name: bad\nextends: [\ndescription: Bad\n")

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("bad.yaml" in error and "invalid YAML" in error for error in result.errors)


def test_loadout_destination_collision_is_an_error(tmp_path: Path) -> None:
    write(
        tmp_path / "rules" / "core" / "a.mdc",
        "---\ndescription: Rule A\n---\n\nA.\n",
    )
    write(
        tmp_path / "rules" / "python" / "b.mdc",
        "---\ndescription: Rule B\n---\n\nB.\n",
    )
    write(
        tmp_path / "loadouts" / "base.yaml",
        "name: base\ndescription: Base\n"
        "rules:\n"
        "  - src: rules/core/a.mdc\n"
        "    dest: .cursor/rules/shared.mdc\n"
        "  - src: rules/python/b.mdc\n"
        "    dest: .cursor/rules/shared.mdc\n",
    )

    result = lint_repo(tmp_path)

    assert not result.ok
    assert any("collision" in error for error in result.errors)


def test_oversized_skill_md_warns_but_does_not_fail(tmp_path: Path) -> None:
    base_repo(tmp_path)
    body = "\n".join(f"line {i}" for i in range(600))
    write(
        tmp_path / "skills" / "demo" / "SKILL.md",
        f"---\nname: demo\ndescription: Demo skill\n---\n\n{body}\n",
    )

    result = lint_repo(tmp_path)

    assert result.ok
    assert any("SKILL.md" in warning and "500" in warning for warning in result.warnings)


def test_long_reference_file_without_toc_warns_but_does_not_fail(tmp_path: Path) -> None:
    base_repo(tmp_path)
    body = "\n".join(f"detail line {i}" for i in range(400))
    write(tmp_path / "skills" / "demo" / "references" / "deep-dive.md", body)

    result = lint_repo(tmp_path)

    assert result.ok
    assert any("references/deep-dive.md" in warning for warning in result.warnings)


def test_long_reference_file_with_toc_does_not_warn(tmp_path: Path) -> None:
    base_repo(tmp_path)
    toc = "\n".join(f"- [Section {i}](#section-{i})" for i in range(5))
    body = "\n".join(f"detail line {i}" for i in range(400))
    write(
        tmp_path / "skills" / "demo" / "references" / "deep-dive.md",
        f"# Deep dive\n\n## Table of Contents\n\n{toc}\n\n{body}",
    )

    result = lint_repo(tmp_path)

    assert result.ok
    assert result.warnings == []
