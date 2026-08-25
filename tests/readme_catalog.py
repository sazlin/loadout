"""Test contract for README catalog hrefs and table parsing.

Independent of generate_readme._primary_href / _directory_href so YAML-vs-catalog
tests are not tautologies.
"""

from __future__ import annotations

import re
from pathlib import Path

from loadout.models import LoadoutDef

HEADING = "## Available loadouts"
EM_DASH = "\u2014"
CATALOG_COLUMNS = ("extends", "agents", "skills", "rules", "mcps", "etc")
NAME_RE = re.compile(r"`([^`]+)`")
_LI_RE = re.compile(r"<li>(.*?)</li>")
_HREF_RE = re.compile(r'<a href="([^"]+)">(?:<code>)?([^<]+)(?:</code>)?</a>')
_CODE_RE = re.compile(r"<code>([^<]+)</code>")


def src_label(src: str) -> str:
    """Return the catalog display name for a loadout src path."""
    path = Path(src)
    return path.stem if path.suffix else path.name


def primary_href(src: str, kind: str, root: Path) -> str:
    """Return the expected catalog href for src (skills → SKILL.md, and so on)."""
    path = Path(src)
    if path.suffix:
        return path.as_posix()
    if kind == "skills":
        return (path / "SKILL.md").as_posix()
    if kind == "mcps":
        readme = path / "README.md"
        return (readme if (root / readme).is_file() else path / "mcp.yaml").as_posix()
    if kind == "hooks":
        source = path / "SOURCE.md"
        return (source if (root / source).is_file() else path / "hook.yaml").as_posix()
    if kind == "agents":
        return (path / f"{path.name}.md").as_posix()
    return path.as_posix()


def listed_items(cell: str) -> list[tuple[str, str | None]]:
    """Parse an HTML <ul> catalog cell into (name, href) pairs."""
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


def catalog_rows(markdown: str) -> dict[str, dict[str, str]]:
    """Parse a loadout catalog table into name → column cells."""
    start = markdown.find(HEADING)
    assert start != -1, f"catalog is missing {HEADING}"
    rest = markdown[start + len(HEADING) :]
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
        names = NAME_RE.findall(cells[0])
        assert names, f"catalog row has no backticked loadout name: {line}"
        name = names[0]
        assert name not in rows, f"duplicate catalog row for {name}"
        rows[name] = dict(zip(CATALOG_COLUMNS, cells[1:7], strict=True))
    return rows


def expected_kind(loadout: LoadoutDef, kind: str, root: Path) -> list[tuple[str, str | None]]:
    """Return expected (name, href) pairs for one catalog kind column."""
    srcs = [entry["src"] for entry in getattr(loadout, kind) if isinstance(entry.get("src"), str)]
    return [(src_label(src), primary_href(src, kind, root)) for src in srcs]


def expected_etc(loadout: LoadoutDef, root: Path) -> list[tuple[str, str | None]]:
    """Return expected Etc. items: hooks plus CLI tool names without hrefs."""
    items = expected_kind(loadout, "hooks", root)
    items.extend((tool.name, None) for tool in loadout.cli_tools)
    return items


def expected_columns(loadout: LoadoutDef, root: Path) -> dict[str, list[tuple[str, str | None]]]:
    """Return expected (name, href) pairs for every catalog kind column."""
    columns = {kind: expected_kind(loadout, kind, root) for kind in ("agents", "skills", "rules", "mcps")}
    columns["etc"] = expected_etc(loadout, root)
    return columns
