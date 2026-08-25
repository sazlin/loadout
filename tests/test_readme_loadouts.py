"""Contracts for the README loadout catalog rule and table."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from loadout.frontmatter import parse_rule
from loadout.models import LoadoutDef, load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
RULE_SRC = "rules/core/readme-loadouts.mdc"
RULE = REPO / RULE_SRC
README = REPO / "README.md"
LOADOUTS_DIR = REPO / "loadouts"
HEADING = "## Available loadouts"
EM_DASH = "\u2014"
CATALOG_COLUMNS = ("extends", "agents", "skills", "rules", "mcps", "etc")
_NAME_RE = re.compile(r"`([^`]+)`")
_LI_RE = re.compile(r"<li>(.*?)</li>")
_HREF_RE = re.compile(r'<a href="([^"]+)">(?:<code>)?([^<]+)(?:</code>)?</a>')
_CODE_RE = re.compile(r"<code>([^<]+)</code>")


def _loadout_names() -> set[str]:
    return {path.stem for path in LOADOUTS_DIR.glob("*.yaml")}


def _available_loadout_rows(readme: str) -> dict[str, dict[str, str]]:
    """Parse the README catalog table into name -> column cells."""
    start = readme.find(HEADING)
    assert start != -1, f"README.md is missing {HEADING}"
    rest = readme[start + len(HEADING) :]
    next_heading = re.search(r"^## ", rest, re.MULTILINE)
    section = rest[: next_heading.start()] if next_heading else rest
    rows: dict[str, dict[str, str]] = {}
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        is_header = cells[0] == "Loadout"
        is_separator = cells[0].replace("-", "") == ""
        if len(cells) < 7 or is_header or is_separator:
            continue
        names = _NAME_RE.findall(cells[0])
        assert names, f"catalog row has no backticked loadout name: {line}"
        name = names[0]
        assert name not in rows, f"duplicate catalog row for {name}"
        rows[name] = dict(zip(CATALOG_COLUMNS, cells[1:7], strict=True))
    return rows


def _listed_items(cell: str) -> list[tuple[str, str | None]]:
    if cell in {EM_DASH, "-", "–", ""}:
        return []
    items: list[tuple[str, str | None]] = []
    for inner in _LI_RE.findall(cell):
        linked = _HREF_RE.search(inner)
        if linked:
            items.append((linked.group(2), linked.group(1)))
            continue
        code = _CODE_RE.search(inner)
        assert code, inner
        items.append((code.group(1), None))
    return items


def _src_label(src: str) -> str:
    path = Path(src)
    return path.stem if path.suffix else path.name


def _primary_href(src: str, kind: str) -> str:
    path = Path(src)
    if path.suffix:
        return path.as_posix()
    if kind == "skills":
        return (path / "SKILL.md").as_posix()
    if kind == "mcps":
        readme = path / "README.md"
        return (readme if (REPO / readme).is_file() else path / "mcp.yaml").as_posix()
    if kind == "hooks":
        source = path / "SOURCE.md"
        return (source if (REPO / source).is_file() else path / "hook.yaml").as_posix()
    if kind == "agents":
        return (path / f"{path.name}.md").as_posix()
    return path.as_posix()


def _expected_kind(loadout: LoadoutDef, kind: str) -> list[tuple[str, str | None]]:
    srcs = [entry["src"] for entry in getattr(loadout, kind) if isinstance(entry.get("src"), str)]
    return [(_src_label(src), _primary_href(src, kind)) for src in srcs]


def _expected_etc(loadout: LoadoutDef) -> list[tuple[str, str | None]]:
    items = _expected_kind(loadout, "hooks")
    items.extend((tool.name, None) for tool in loadout.cli_tools)
    return items


def _extends_from_cell(cell: str) -> list[str]:
    names = _NAME_RE.findall(cell)
    if names:
        return names
    if cell in {EM_DASH, "-", "–", ""}:
        return []
    raise AssertionError(f"unrecognized Extends cell: {cell!r}")


def test_base_loadout_includes_readme_loadouts_rule() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    assert RULE_SRC in {entry["src"] for entry in loadout.rules}


def test_readme_loadouts_rule_is_glob_scoped_to_catalog_sources() -> None:
    text = RULE.read_text()
    meta = parse_rule(RULE, text)
    assert meta.always_apply is False
    assert meta.globs == ["loadouts/*.yaml"]
    lowered = meta.description.lower()
    assert "readme" in lowered
    assert "loadout" in lowered


def test_readme_loadouts_rule_requires_same_change_catalog_update() -> None:
    text = RULE.read_text().lower()
    assert "available loadouts" in text
    assert "same change" in text or "same commit" in text
    assert "extends" in text
    assert "agents" in text
    assert "skills" in text
    assert "rules" in text
    assert "mcps" in text
    assert "etc" in text
    assert "what you get" not in text
    assert any(word in text for word in ("later", "follow-up", "follow up"))


def test_readme_available_loadouts_lists_every_loadout() -> None:
    text = README.read_text()
    assert "| Loadout | Extends | Agents | Skills | Rules | MCPs | Etc. |" in text
    rows = _available_loadout_rows(text)
    on_disk = _loadout_names()
    assert on_disk == set(rows), f"README catalog drift: missing={on_disk - set(rows)} extra={set(rows) - on_disk}"


def test_readme_available_loadouts_extends_match_yaml() -> None:
    rows = _available_loadout_rows(README.read_text())
    for name in sorted(_loadout_names()):
        loadout = load_loadout(LOADOUTS_DIR / f"{name}.yaml")
        assert _extends_from_cell(rows[name]["extends"]) == loadout.extends


def test_readme_catalog_lists_own_artifacts_as_linked_names() -> None:
    rows = _available_loadout_rows(README.read_text())
    for name in sorted(_loadout_names()):
        loadout = load_loadout(LOADOUTS_DIR / f"{name}.yaml")
        cells = rows[name]
        expected = {
            "agents": _expected_kind(loadout, "agents"),
            "skills": _expected_kind(loadout, "skills"),
            "rules": _expected_kind(loadout, "rules"),
            "mcps": _expected_kind(loadout, "mcps"),
            "etc": _expected_etc(loadout),
        }
        for kind, items in expected.items():
            listed = _listed_items(cells[kind])
            assert listed == items, f"{name} {kind}: {cells[kind]!r}"
            if not items:
                assert cells[kind] == EM_DASH, f"{name} {kind} should be an em dash"
            for item_name, href in items:
                if href is None:
                    continue
                assert (REPO / href).is_file(), f"{name} {kind} {item_name} -> {href}"


def test_readme_omits_loadout_spec_and_stale_version_pins() -> None:
    text = README.read_text()
    assert "loadout-spec.md" not in text
    assert "v0.5.0" not in text
    assert "loadout@main" not in text


def test_base_sync_vendors_readme_loadouts_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [base]\n")
    sync(project)
    dest = project / ".cursor/rules/readme-loadouts.mdc"
    assert dest.is_file()
    assert "Available loadouts" in dest.read_text()
