#!/usr/bin/env python3
"""Fill generated README sections from loadout YAML on disk."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

from loadout.models import LoadoutDef, load_loadout

CATALOG_START = "<!-- generated:loadouts-catalog:start -->"
CATALOG_END = "<!-- generated:loadouts-catalog:end -->"
OPTIONAL_START = "<!-- generated:optional:loadouts-section:start -->"
OPTIONAL_END = "<!-- generated:optional:loadouts-section:end -->"
BANNER_START = "<!-- generated:optional:banner:start -->"
BANNER_END = "<!-- generated:optional:banner:end -->"
BANNER_RELATIVE = Path("docs/assets/loadout-banner.jpg")
EM_DASH = "\u2014"
KIND_ORDER = ("skills", "agents", "hooks", "mcps", "cli_tools", "rules")
MAX_HIGHLIGHTS = 5
TABLE_HEADER = "| Loadout | Extends | What you get |\n| --- | --- | --- |"


def has_loadouts(repo_root: Path) -> bool:
    """Return True when repo_root has at least one loadouts/*.yaml file."""
    directory = repo_root / "loadouts"
    return directory.is_dir() and any(directory.glob("*.yaml"))


def has_banner(repo_root: Path) -> bool:
    """Return True when this repo's README banner file exists on disk."""
    return (repo_root / BANNER_RELATIVE).is_file()


def catalog_markdown(repo_root: Path) -> str:
    """Return the Available loadouts markdown table for repo_root."""
    loadouts = _load_all(repo_root)
    names = sorted(loadouts, key=lambda name: (_depth(name, loadouts), name))
    rows = [TABLE_HEADER]
    for name in names:
        loadout = loadouts[name]
        rows.append(f"| `{name}` | {_extends_cell(loadout)} | {_summary_cell(loadout)} |")
    return "\n".join(rows)


def fill_template(
    template: str,
    *,
    catalog: str,
    has_loadouts: bool,
    has_banner: bool,
) -> str:
    """Replace generated markers. Drop optional blocks whose assets are absent."""
    text = template
    if has_loadouts:
        text = _replace_block(text, CATALOG_START, CATALOG_END, catalog)
    else:
        text = _drop_marked_section(text, OPTIONAL_START, OPTIONAL_END)
    if not has_banner:
        text = _drop_marked_section(text, BANNER_START, BANNER_END)
    return text


def generate_readme(*, repo_root: Path, template: Path, output: Path) -> None:
    """Write output from template with catalog sections filled or removed."""
    present = has_loadouts(repo_root)
    banner = has_banner(repo_root)
    catalog = catalog_markdown(repo_root) if present else ""
    filled = fill_template(
        template.read_text(),
        catalog=catalog,
        has_loadouts=present,
        has_banner=banner,
    )
    output.write_text(filled)


def _load_all(repo_root: Path) -> dict[str, LoadoutDef]:
    loadouts: dict[str, LoadoutDef] = {}
    for path in sorted((repo_root / "loadouts").glob("*.yaml")):
        loadout = load_loadout(path)
        loadouts[loadout.name] = loadout
    return loadouts


def _depth(name: str, loadouts: dict[str, LoadoutDef]) -> int:
    return _depth_from(name, loadouts, frozenset())


def _depth_from(name: str, loadouts: dict[str, LoadoutDef], seen: frozenset[str]) -> int:
    if name in seen:
        return 0
    loadout = loadouts.get(name)
    if loadout is None or not loadout.extends:
        return 0
    parents = [_depth_from(parent, loadouts, seen | {name}) for parent in loadout.extends]
    return 1 + max(parents)


def _extends_cell(loadout: LoadoutDef) -> str:
    if not loadout.extends:
        return EM_DASH
    return ", ".join(f"`{name}`" for name in loadout.extends)


def _summary_cell(loadout: LoadoutDef) -> str:
    description = " ".join(loadout.description.split())
    highlights = _highlights(loadout)
    if not highlights:
        return description
    listed = ", ".join(f"`{name}`" for name in highlights)
    return f"{description} ({listed})"


def _highlights(loadout: LoadoutDef) -> list[str]:
    grouped = _grouped_names(loadout)
    picked: list[str] = []
    _take_one_per_kind(grouped, picked)
    _fill_remaining(grouped, picked)
    return picked[:MAX_HIGHLIGHTS]


def _grouped_names(loadout: LoadoutDef) -> dict[str, list[str]]:
    return {
        "rules": _labels_from_entries(loadout.rules),
        "skills": _labels_from_entries(loadout.skills),
        "hooks": _labels_from_entries(loadout.hooks),
        "agents": _labels_from_entries(loadout.agents),
        "mcps": _labels_from_entries(loadout.mcps),
        "cli_tools": [tool.name for tool in loadout.cli_tools],
    }


def _labels_from_entries(entries: list[Mapping[str, object]]) -> list[str]:
    labels: list[str] = []
    for entry in entries:
        src = entry.get("src")
        if isinstance(src, str) and src:
            labels.append(_src_label(src))
    return labels


def _src_label(src: str) -> str:
    path = Path(src)
    return path.stem if path.suffix else path.name


def _take_one_per_kind(grouped: dict[str, list[str]], picked: list[str]) -> None:
    for kind in KIND_ORDER:
        unused = [name for name in grouped[kind] if name not in picked]
        if unused:
            picked.append(unused[0])


def _fill_remaining(grouped: dict[str, list[str]], picked: list[str]) -> None:
    for kind in KIND_ORDER:
        for name in grouped[kind]:
            if name not in picked:
                picked.append(name)
            if len(picked) >= MAX_HIGHLIGHTS:
                return


def _replace_block(text: str, start: str, end: str, body: str) -> str:
    start_at = text.find(start)
    end_at = text.find(end)
    if start_at == -1 or end_at == -1 or end_at < start_at:
        raise SystemExit(f"template missing markers {start} / {end}")
    inner_from = start_at + len(start)
    return text[:inner_from] + "\n" + body.rstrip() + "\n" + text[end_at:]


def _drop_marked_section(text: str, start: str, end: str) -> str:
    start_at = text.find(start)
    end_at = text.find(end)
    if start_at == -1 or end_at == -1 or end_at < start_at:
        return text
    end_at += len(end)
    return text[:start_at].rstrip() + "\n\n" + text[end_at:].lstrip()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    generate_readme(repo_root=args.repo_root, template=args.template, output=args.output)


if __name__ == "__main__":
    main()
