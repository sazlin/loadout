from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from loadout import __version__
from loadout.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "mini_loadout"


def write_manifest(loadouts: str = "[python]", *, extra: str = "") -> None:
    Path(".loadout.yaml").write_text(f"source: https://example.com/loadout\nref: v1.0.0\nloadouts: {loadouts}\n{extra}")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_version_flag_prints_the_package_version(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_sync_writes_files_and_exits_zero(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        write_manifest()

        result = runner.invoke(main, ["sync"], env={"LOADOUT_PATH": str(FIXTURE)})

        assert result.exit_code == 0, result.output
        assert Path(".cursor/rules/a.mdc").is_file()
        assert Path(".claude/skills/demo/SKILL.md").is_file()
        assert "added" in result.output


def test_sync_without_manifest_exits_with_validation_error_code(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["sync"], env={"LOADOUT_PATH": str(FIXTURE)})

        assert result.exit_code == 2
        assert "error" in result.output.lower()


def test_sync_with_a_malformed_manifest_exits_two(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        Path(".loadout.yaml").write_text("source: https://example.com/loadout\nloadouts: [\n")

        result = runner.invoke(main, ["sync"], env={"LOADOUT_PATH": str(FIXTURE)})

        assert result.exit_code == 2, result.output
        assert "invalid YAML" in result.output
        assert ".loadout.yaml" in result.output


def test_sync_with_a_malformed_lockfile_exits_two(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        write_manifest()
        Path(".loadout.lock").write_text('{"lockfile_version": 1,\n')

        result = runner.invoke(main, ["sync"], env={"LOADOUT_PATH": str(FIXTURE)})

        assert result.exit_code == 2, result.output
        assert "invalid JSON" in result.output
        assert ".loadout.lock" in result.output


def test_resolve_with_a_malformed_manifest_exits_two(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        Path(".loadout.yaml").write_text("loadouts: [base\n")

        result = runner.invoke(main, ["resolve", "--list"], env={"LOADOUT_PATH": str(FIXTURE)})

        assert result.exit_code == 2, result.output
        assert "invalid YAML" in result.output


def test_sync_check_reports_drift_with_exit_code_one(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        write_manifest()
        env = {"LOADOUT_PATH": str(FIXTURE)}
        runner.invoke(main, ["sync"], env=env)
        Path(".cursor/rules/a.mdc").write_text("hand edited\n")

        result = runner.invoke(main, ["sync", "--check"], env=env)

        assert result.exit_code == 1
        assert "drift" in result.output.lower()


def test_sync_check_passes_on_a_clean_tree(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        write_manifest()
        env = {"LOADOUT_PATH": str(FIXTURE)}
        runner.invoke(main, ["sync"], env=env)

        result = runner.invoke(main, ["sync", "--check"], env=env)

        assert result.exit_code == 0


def test_init_writes_manifest_with_defaults(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "--loadouts", "base,python"])

        assert result.exit_code == 0, result.output
        manifest = yaml.safe_load(Path(".loadout.yaml").read_text())
        assert manifest["loadouts"] == ["base", "python"]
        assert manifest["source"] == "https://github.com/sazlin/loadout"
        assert manifest["ref"] == "main"


def test_init_keeps_every_comma_separated_name(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "--loadouts", "base,python,pr_review_harness"])

        assert result.exit_code == 0, result.output
        manifest = yaml.safe_load(Path(".loadout.yaml").read_text())
        assert manifest["loadouts"] == ["base", "python", "pr_review_harness"]


def test_init_strips_whitespace_around_loadout_names(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "--loadouts", " base , python "])

        assert result.exit_code == 0, result.output
        manifest = yaml.safe_load(Path(".loadout.yaml").read_text())
        assert manifest["loadouts"] == ["base", "python"]


def test_init_preserves_loadout_name_order(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "--loadouts", "python,base,terraform"])

        assert result.exit_code == 0, result.output
        manifest = yaml.safe_load(Path(".loadout.yaml").read_text())
        assert manifest["loadouts"] == ["python", "base", "terraform"]


def test_init_accepts_custom_source_and_ref(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                "init",
                "--loadouts",
                "base",
                "--source",
                "https://example.com/org/loadout",
                "--ref",
                "v2.3.0",
            ],
        )

        assert result.exit_code == 0, result.output
        manifest = yaml.safe_load(Path(".loadout.yaml").read_text())
        assert manifest["source"] == "https://example.com/org/loadout"
        assert manifest["ref"] == "v2.3.0"


def test_init_refuses_to_overwrite_an_existing_manifest(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        write_manifest()

        result = runner.invoke(main, ["init", "--loadouts", "base"])

        assert result.exit_code == 2
        assert "already exists" in result.output


def test_init_rejects_empty_loadouts_list(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "--loadouts", " , "])

        assert result.exit_code == 2


def test_resolve_list_prints_src_to_dest_table(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        write_manifest()

        result = runner.invoke(main, ["resolve", "--list"], env={"LOADOUT_PATH": str(FIXTURE)})

        assert result.exit_code == 0, result.output
        assert "rules/core/a.mdc -> .cursor/rules/a.mdc" in result.output
        assert "skills/demo/SKILL.md -> .claude/skills/demo/SKILL.md" in result.output


def test_resolve_list_prints_cli_tools(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        source = Path("source")
        shutil.copytree(FIXTURE, source)
        (source / "loadouts" / "python.yaml").write_text(
            "name: python\nextends: [base]\ndescription: Python\n"
            "rules:\n  - src: rules/python/b.mdc\n"
            "cli_tools:\n  - name: jq\n    command: command -v jq || true\n"
        )
        write_manifest()

        result = runner.invoke(main, ["resolve", "--list"], env={"LOADOUT_PATH": str(source.resolve())})

        assert result.exit_code == 0, result.output
        assert "cli_tools: jq: command -v jq || true" in result.output


def test_resolve_without_list_flag_is_a_usage_error(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        write_manifest()

        result = runner.invoke(main, ["resolve"], env={"LOADOUT_PATH": str(FIXTURE)})

        assert result.exit_code != 0


def test_lint_passes_on_a_clean_loadout_repo(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        for name in ("rules", "skills", "hooks", "agents", "mcps", "loadouts"):
            shutil.copytree(FIXTURE / name, Path(name))

        result = runner.invoke(main, ["lint"])

        assert result.exit_code == 0, result.output


def test_lint_fails_on_an_orphan_file(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        for name in ("rules", "skills", "hooks", "agents", "mcps", "loadouts"):
            shutil.copytree(FIXTURE / name, Path(name))
        orphan = Path("rules/python/orphan.mdc")
        orphan.write_text("---\ndescription: Unused\n---\n\nUnused.\n")

        result = runner.invoke(main, ["lint"])

        assert result.exit_code == 2
        assert "orphan" in result.output.lower()


def test_lint_fails_when_loadout_extends_missing_parent(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        for name in ("rules", "skills", "hooks", "agents", "mcps", "loadouts"):
            shutil.copytree(FIXTURE / name, Path(name))
        Path("loadouts/child.yaml").write_text("name: child\nextends: [missing]\ndescription: Child\n")

        result = runner.invoke(main, ["lint"])

        assert result.exit_code == 2
        assert "Loadout not found: missing" in result.output


def test_update_rewrites_ref_syncs_and_prints_changelog_slice(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        source = Path("source")
        shutil.copytree(FIXTURE, source)
        (source / "CHANGELOG.md").write_text(
            "# CHANGELOG\n\n"
            "## 3.0.0\n\n- Third release notes\n\n"
            "## 2.0.0\n\n- Second release notes\n\n"
            "## 1.0.0\n\n- First release notes\n"
        )
        write_manifest()

        result = runner.invoke(main, ["update", "--to", "v3.0.0"], env={"LOADOUT_PATH": str(source)})

        assert result.exit_code == 0, result.output
        manifest = yaml.safe_load(Path(".loadout.yaml").read_text())
        assert manifest["ref"] == "v3.0.0"
        assert "Third release notes" in result.output
        assert "Second release notes" in result.output
        assert "First release notes" not in result.output


def test_update_runs_cli_tools(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        source = Path("source")
        shutil.copytree(FIXTURE, source)
        (source / "CHANGELOG.md").write_text("# CHANGELOG\n\n## 2.0.0\n\n- Next\n\n## 1.0.0\n\n- First\n")
        (source / "loadouts" / "python.yaml").write_text(
            "name: python\nextends: [base]\ndescription: Python\n"
            "rules:\n  - src: rules/python/b.mdc\n"
            "cli_tools:\n  - name: marker\n    command: echo updated > marker.txt\n"
        )
        write_manifest()

        result = runner.invoke(main, ["update", "--to", "v2.0.0"], env={"LOADOUT_PATH": str(source.resolve())})

        assert result.exit_code == 0, result.output
        assert Path("marker.txt").read_text() == "updated\n"
        assert "loadout: cli_tools: marker: ok" in result.output


def test_update_without_manifest_exits_with_validation_error_code(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["update", "--to", "v2.0.0"])

        assert result.exit_code == 2
