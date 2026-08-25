"""Contracts for the repo-local generating-readme skill and generator script."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from readme_catalog import (
    EM_DASH,
    HEADING,
    NAME_RE,
    catalog_rows,
    expected_etc,
    expected_kind,
    listed_items,
)

from loadout.frontmatter import parse_skill_md
from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO / ".claude" / "skills" / "generating-readme"
SKILL_MD = SKILL_ROOT / "SKILL.md"
SCRIPT = SKILL_ROOT / "scripts" / "generate_readme.py"
TEMPLATE = SKILL_ROOT / "templates" / "README.md"
BEST_PRACTICES = SKILL_ROOT / "references" / "readme-best-practices.md"
EVALS = SKILL_ROOT / "evals" / "evals.json"
MINI = REPO / "tests" / "fixtures" / "mini_loadout"
BANNER = "docs/assets/loadout-banner.jpg"
CATALOG_START = "<!-- generated:loadouts-catalog:start -->"
CATALOG_END = "<!-- generated:loadouts-catalog:end -->"
OPTIONAL_START = "<!-- generated:optional:loadouts-section:start -->"
OPTIONAL_END = "<!-- generated:optional:loadouts-section:end -->"
BANNER_START = "<!-- generated:optional:banner:start -->"
BANNER_END = "<!-- generated:optional:banner:end -->"


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_readme", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Skill scripts are not an installed package; load from path like tests/impl_eval_score.py.
_GENERATOR = _load_generator()


def _generator() -> ModuleType:
    return _GENERATOR


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _loadout_names(root: Path) -> set[str]:
    return {path.stem for path in (root / "loadouts").glob("*.yaml")}


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd or REPO,
    )


def test_skill_md_is_valid_and_discoverable() -> None:
    assert SKILL_MD.is_file()
    parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name="generating-readme")
    text = SKILL_MD.read_text()
    assert "Use when" in text
    assert BANNER in text
    assert "loadout" in text.lower()


def test_skill_is_not_attached_to_any_loadout() -> None:
    needle = "generating-readme"
    for path in sorted((REPO / "loadouts").glob("*.yaml")):
        assert needle not in path.read_text(), f"{path.name} must not vendor {needle}"


def test_best_practices_reference_exists() -> None:
    text = BEST_PRACTICES.read_text()
    lowered = text.lower()
    assert "anti-pattern" in lowered or "antipattern" in lowered
    assert "badge" in lowered
    assert "quick start" in lowered


def test_template_keeps_banner_and_catalog_markers() -> None:
    text = TEMPLATE.read_text()
    assert BANNER in text
    assert CATALOG_START in text
    assert CATALOG_END in text
    assert OPTIONAL_START in text
    assert OPTIONAL_END in text
    assert BANNER_START in text
    assert BANNER_END in text
    assert HEADING in text


def test_evals_json_lists_fixture_files() -> None:
    payload = EVALS.read_text()
    assert "evals" in payload
    assert (SKILL_ROOT / "evals" / "files" / "tiny-readme.template.md").is_file()


def test_mini_catalog_lists_every_loadout() -> None:
    markdown = _generator().catalog_markdown(MINI)
    assert "| Loadout | Extends | Agents | Skills | Rules | MCPs | Etc. |" in markdown
    rows = catalog_rows(f"{HEADING}\n\n{markdown}")
    assert set(rows) == _loadout_names(MINI)


def test_mini_catalog_extends_and_linked_artifacts_match_yaml() -> None:
    markdown = _generator().catalog_markdown(MINI)
    rows = catalog_rows(f"{HEADING}\n\n{markdown}")
    for name, cells in rows.items():
        loadout = load_loadout(MINI / "loadouts" / f"{name}.yaml")
        listed = NAME_RE.findall(cells["extends"])
        assert listed == loadout.extends
        expected = {
            "agents": expected_kind(loadout, "agents", MINI),
            "skills": expected_kind(loadout, "skills", MINI),
            "rules": expected_kind(loadout, "rules", MINI),
            "mcps": expected_kind(loadout, "mcps", MINI),
            "etc": expected_etc(loadout, MINI),
        }
        for kind, items in expected.items():
            assert listed_items(cells[kind]) == items, (name, kind, cells[kind])
            if not items:
                assert cells[kind] == EM_DASH, f"{name} {kind} should be an em dash"


def test_fill_template_replaces_catalog_and_keeps_banner() -> None:
    generator = _generator()
    template = (
        f'<img src="{BANNER}" alt="banner" />\n\n'
        f"{OPTIONAL_START}\n{HEADING}\n\n{CATALOG_START}\nOLD\n{CATALOG_END}\n"
        f"{OPTIONAL_END}\n"
    )
    filled = generator.fill_template(
        template,
        catalog=generator.catalog_markdown(MINI),
        loadouts_present=True,
        banner_present=True,
    )
    assert BANNER in filled
    assert "OLD" not in filled
    assert "`base`" in filled
    assert "`python`" in filled
    assert CATALOG_START in filled


def test_fill_template_missing_catalog_markers_raises_value_error() -> None:
    generator = _generator()
    with pytest.raises(ValueError, match="generated:loadouts-catalog"):
        generator.fill_template(
            "no catalog markers",
            catalog="table",
            loadouts_present=True,
            banner_present=True,
        )


def test_cli_missing_catalog_markers_exits_nonzero(tmp_path: Path) -> None:
    template = tmp_path / "broken.md"
    template.write_text("no catalog markers\n")
    out = tmp_path / "README.md"
    completed = _run_cli(
        "--repo-root",
        str(MINI),
        "--template",
        str(template),
        "--output",
        str(out),
    )
    assert completed.returncode != 0
    message = completed.stderr + completed.stdout
    assert "generated:loadouts-catalog" in message


def test_fill_template_drops_optional_section_without_loadouts(tmp_path: Path) -> None:
    generator = _generator()
    template = f"intro\n{OPTIONAL_START}\n{HEADING}\n{OPTIONAL_END}\nlicense\n"
    filled = generator.fill_template(
        template,
        catalog="",
        loadouts_present=False,
        banner_present=True,
    )
    assert HEADING not in filled
    assert OPTIONAL_START not in filled
    assert "intro" in filled
    assert "license" in filled
    empty = tmp_path / "empty-repo"
    empty.mkdir()
    assert generator.has_loadouts(empty) is False
    assert generator.has_banner(empty) is False


def test_this_repo_catalog_satisfies_readme_contracts() -> None:
    markdown = _generator().catalog_markdown(REPO)
    rows = catalog_rows(f"{HEADING}\n\n{markdown}")
    names = _loadout_names(REPO)
    assert set(rows) == names
    for name in names:
        loadout = load_loadout(REPO / "loadouts" / f"{name}.yaml")
        cells = rows[name]
        assert NAME_RE.findall(cells["extends"]) == loadout.extends
        expected = {
            "agents": expected_kind(loadout, "agents", REPO),
            "skills": expected_kind(loadout, "skills", REPO),
            "rules": expected_kind(loadout, "rules", REPO),
            "mcps": expected_kind(loadout, "mcps", REPO),
            "etc": expected_etc(loadout, REPO),
        }
        for kind, items in expected.items():
            assert listed_items(cells[kind]) == items, (name, kind, cells[kind])
            for item_name, href in items:
                if href is None:
                    continue
                assert (REPO / href).is_file(), f"{name} {kind} {item_name} -> {href}"


def test_cli_writes_filled_readme(tmp_path: Path) -> None:
    out = tmp_path / "README.md"
    completed = _run_cli("--repo-root", str(MINI), "--template", str(TEMPLATE), "--output", str(out))
    assert completed.returncode == 0, completed.stderr
    text = out.read_text()
    version = _generator().latest_tag(MINI)
    assert "`base`" in text
    assert BANNER not in text
    assert CATALOG_START in text
    assert "{{VERSION}}" not in text
    assert f"loadout@{version}" in text
    assert "loadout-spec.md" not in text


def test_fill_template_drops_banner_when_asset_missing() -> None:
    generator = _generator()
    template = f'{BANNER_START}\n<img src="{BANNER}" alt="banner" />\n{BANNER_END}\n# Title\n'
    filled = generator.fill_template(template, catalog="", loadouts_present=False, banner_present=False)
    assert BANNER not in filled
    assert BANNER_START not in filled
    assert "# Title" in filled


def test_cli_keeps_banner_when_asset_exists(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(MINI, repo)
    banner = repo / BANNER
    banner.parent.mkdir(parents=True, exist_ok=True)
    banner.write_bytes(b"fake-image")
    out = tmp_path / "README.md"
    completed = _run_cli("--repo-root", str(repo), "--template", str(TEMPLATE), "--output", str(out))
    assert completed.returncode == 0, completed.stderr
    text = out.read_text()
    assert BANNER in text
    assert BANNER_START in text


def test_catalog_is_deterministic() -> None:
    generator = _generator()
    assert generator.catalog_markdown(MINI) == generator.catalog_markdown(MINI)
    assert generator.catalog_markdown(REPO) == generator.catalog_markdown(REPO)


def test_latest_tag_returns_newest_version_tag(tmp_path: Path) -> None:
    repo = tmp_path / "tagged"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "dev@example.com")
    _git(repo, "config", "user.name", "Dev")
    (repo / "marker.txt").write_text("ok\n")
    _git(repo, "add", "marker.txt")
    _git(repo, "commit", "-m", "init")
    _git(repo, "tag", "v0.9.0")
    _git(repo, "tag", "v0.10.0")
    _git(repo, "tag", "v0.2.0")
    assert _generator().latest_tag(repo) == "v0.10.0"


def test_latest_tag_falls_back_to_pyproject_version(tmp_path: Path) -> None:
    repo = tmp_path / "untagged"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "1.2.3"\n')
    assert _generator().latest_tag(repo) == "v1.2.3"


def test_template_examples_use_version_placeholder_not_stale_pins() -> None:
    text = TEMPLATE.read_text()
    assert "{{VERSION}}" in text
    assert "v0.5.0" not in text
    assert "loadout@main" not in text
    assert "loadout-spec.md" not in text
    assert "ref: {{VERSION}}" in text


def test_fill_template_substitutes_version_placeholders() -> None:
    generator = _generator()
    template = "uvx --from git+https://example@{{VERSION}} just release {{VERSION_NUMBER}}\n"
    filled = generator.fill_template(
        template,
        catalog="",
        loadouts_present=False,
        banner_present=True,
        version="v9.9.9",
    )
    assert filled == "uvx --from git+https://example@v9.9.9 just release 9.9.9\n"
    assert "{{VERSION}}" not in filled


def test_skill_and_evals_omit_loadout_spec() -> None:
    skill = SKILL_MD.read_text()
    evals = EVALS.read_text()
    assert "loadout-spec" not in skill
    assert "loadout-spec" not in evals
    assert "What you get" not in evals
