"""Contracts for the repo-local generating-readme skill and audit script."""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

from loadout.frontmatter import parse_skill_md
from loadout.models import LoadoutDef, load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO / ".claude" / "skills" / "generating-readme"
SKILL_MD = SKILL_ROOT / "SKILL.md"
SCRIPT = SKILL_ROOT / "scripts" / "audit_loadouts.py"
TEMPLATE = SKILL_ROOT / "templates" / "README.md"
BEST_PRACTICES = SKILL_ROOT / "references" / "readme-best-practices.md"
EVALS = SKILL_ROOT / "evals" / "evals.json"
MINI = REPO / "tests" / "fixtures" / "mini_loadout"
BANNER = "docs/assets/loadout-banner.jpg"
HEADING = "## Available loadouts"
_NAME_RE = re.compile(r"`([^`]+)`")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
CATALOG_START = "<!-- generated:loadouts-catalog:start -->"
CATALOG_END = "<!-- generated:loadouts-catalog:end -->"
OPTIONAL_START = "<!-- generated:optional:loadouts-section:start -->"
OPTIONAL_END = "<!-- generated:optional:loadouts-section:end -->"
BANNER_START = "<!-- generated:optional:banner:start -->"
BANNER_END = "<!-- generated:optional:banner:end -->"


def _audit():
    spec = importlib.util.spec_from_file_location("audit_loadouts", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _collapsed(text: str) -> str:
    return _NON_ALNUM.sub("", text.lower())


def _own_artifact_names(loadout: LoadoutDef) -> list[str]:
    names: list[str] = []
    for group in (loadout.rules, loadout.skills, loadout.hooks, loadout.agents, loadout.mcps):
        for entry in group:
            src = entry.get("src")
            if not isinstance(src, str):
                continue
            path = Path(src)
            names.append(path.stem if path.suffix else path.name)
    names.extend(tool.name for tool in loadout.cli_tools)
    return names


def _catalog_rows(markdown: str) -> dict[str, tuple[str, str]]:
    start = markdown.find(HEADING)
    assert start != -1, markdown
    rest = markdown[start + len(HEADING) :]
    next_heading = re.search(r"^## ", rest, re.MULTILINE)
    section = rest[: next_heading.start()] if next_heading else rest
    rows: dict[str, tuple[str, str]] = {}
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 3 or cells[0] in {"Loadout", ""} or set(cells[0]) <= {"-"}:
            continue
        names = _NAME_RE.findall(cells[0])
        assert names, line
        rows[names[0]] = (cells[1], cells[2])
    return rows


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
    markdown = _audit().catalog_markdown(MINI)
    rows = _catalog_rows(f"{HEADING}\n\n{markdown}")
    assert set(rows) == _loadout_names(MINI)


def test_mini_catalog_extends_and_artifacts_match_yaml() -> None:
    markdown = _audit().catalog_markdown(MINI)
    rows = _catalog_rows(f"{HEADING}\n\n{markdown}")
    for name, (extends_cell, summary) in rows.items():
        loadout = load_loadout(MINI / "loadouts" / f"{name}.yaml")
        listed = _NAME_RE.findall(extends_cell)
        if not listed:
            assert loadout.extends == []
        else:
            assert listed == loadout.extends
        artifacts = _own_artifact_names(loadout)
        if not artifacts:
            continue
        collapsed_summary = _collapsed(summary)
        assert any(_collapsed(artifact) in collapsed_summary for artifact in artifacts), summary


def test_fill_template_replaces_catalog_and_keeps_banner() -> None:
    audit = _audit()
    template = (
        f'<img src="{BANNER}" alt="banner" />\n\n'
        f"{OPTIONAL_START}\n{HEADING}\n\n{CATALOG_START}\nOLD\n{CATALOG_END}\n"
        f"{OPTIONAL_END}\n"
    )
    filled = audit.fill_template(
        template,
        catalog=audit.catalog_markdown(MINI),
        has_loadouts=True,
        has_banner=True,
    )
    assert BANNER in filled
    assert "OLD" not in filled
    assert "`base`" in filled
    assert "`python`" in filled
    assert CATALOG_START in filled


def test_fill_template_drops_optional_section_without_loadouts(tmp_path: Path) -> None:
    audit = _audit()
    template = f"intro\n{OPTIONAL_START}\n{HEADING}\n{OPTIONAL_END}\nlicense\n"
    filled = audit.fill_template(
        template,
        catalog="",
        has_loadouts=False,
        has_banner=True,
    )
    assert HEADING not in filled
    assert OPTIONAL_START not in filled
    assert "intro" in filled
    assert "license" in filled
    empty = tmp_path / "empty-repo"
    empty.mkdir()
    assert audit.has_loadouts(empty) is False
    assert audit.has_banner(empty) is False


def test_this_repo_catalog_satisfies_readme_contracts() -> None:
    markdown = _audit().catalog_markdown(REPO)
    rows = _catalog_rows(f"{HEADING}\n\n{markdown}")
    names = _loadout_names(REPO)
    assert set(rows) == names
    for name in names:
        loadout = load_loadout(REPO / "loadouts" / f"{name}.yaml")
        extends_cell, summary = rows[name]
        listed = _NAME_RE.findall(extends_cell)
        assert listed == loadout.extends
        artifacts = _own_artifact_names(loadout)
        if artifacts:
            collapsed_summary = _collapsed(summary)
            assert any(_collapsed(artifact) in collapsed_summary for artifact in artifacts), (
                name,
                summary,
                artifacts,
            )


def test_cli_writes_filled_readme(tmp_path: Path) -> None:
    out = tmp_path / "README.md"
    completed = _run_cli("--repo-root", str(MINI), "--template", str(TEMPLATE), "--output", str(out))
    assert completed.returncode == 0, completed.stderr
    text = out.read_text()
    assert "`base`" in text
    assert BANNER not in text
    assert CATALOG_START in text


def test_fill_template_drops_banner_when_asset_missing() -> None:
    audit = _audit()
    template = f'{BANNER_START}\n<img src="{BANNER}" alt="banner" />\n{BANNER_END}\n# Title\n'
    filled = audit.fill_template(template, catalog="", has_loadouts=False, has_banner=False)
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
    audit = _audit()
    assert audit.catalog_markdown(MINI) == audit.catalog_markdown(MINI)
    assert audit.catalog_markdown(REPO) == audit.catalog_markdown(REPO)
