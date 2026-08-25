#!/usr/bin/env python3
"""Fill generated README sections from loadout YAML on disk."""

from __future__ import annotations

import argparse
import re
import subprocess
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
VERSION_TOKEN = "{{VERSION}}"
VERSION_NUMBER_TOKEN = "{{VERSION_NUMBER}}"
TABLE_HEADER = (
    "| Loadout | Extends | Agents | Skills | Rules | MCPs | Etc. |\n| --- | --- | --- | --- | --- | --- | --- |"
)
PYPROJECT_VERSION_RE = re.compile(r'(?m)^version\s*=\s*"([^"]+)"')
FALLBACK_TAG = "v0.0.0"


def has_loadouts(repo_root: Path) -> bool:
    """Return True when repo_root has at least one loadouts/*.yaml file."""
    directory = repo_root / "loadouts"
    return directory.is_dir() and any(directory.glob("*.yaml"))


def has_banner(repo_root: Path) -> bool:
    """Return True when this repo's README banner file exists on disk."""
    return (repo_root / BANNER_RELATIVE).is_file()


def latest_tag(repo_root: Path) -> str:
    """Return the newest git tag at repo_root, or v{pyproject version}."""
    tags = _git_version_tags(repo_root)
    if tags:
        return tags[0]
    return _pyproject_tag(repo_root)


def catalog_markdown(repo_root: Path) -> str:
    """Return the Available loadouts markdown table for repo_root."""
    loadouts = _load_all(repo_root)
    names = sorted(loadouts, key=lambda name: (_depth(name, loadouts), name))
    rows = [TABLE_HEADER]
    for name in names:
        rows.append(_row(loadouts[name], repo_root))
    return "\n".join(rows)


def fill_template(
    template: str,
    *,
    catalog: str,
    has_loadouts: bool,
    has_banner: bool,
    version: str = "",
) -> str:
    """Replace generated markers. Drop optional blocks whose assets are absent."""
    text = _apply_version(template, version)
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
        version=latest_tag(repo_root),
    )
    output.write_text(filled)


def _apply_version(template: str, version: str) -> str:
    if not version:
        return template
    # {{VERSION}} is a prefix of {{VERSION_NUMBER}}, so the longer token must be substituted first.
    text = template.replace(VERSION_NUMBER_TOKEN, version.lstrip("v"))
    return text.replace(VERSION_TOKEN, version)


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


def _row(loadout: LoadoutDef, repo_root: Path) -> str:
    cells = [
        f"`{loadout.name}`",
        _extends_cell(loadout),
        _kind_cell(loadout, "agents", repo_root),
        _kind_cell(loadout, "skills", repo_root),
        _kind_cell(loadout, "rules", repo_root),
        _kind_cell(loadout, "mcps", repo_root),
        _etc_cell(loadout, repo_root),
    ]
    return "| " + " | ".join(cells) + " |"


def _extends_cell(loadout: LoadoutDef) -> str:
    if not loadout.extends:
        return EM_DASH
    return ", ".join(f"`{name}`" for name in loadout.extends)


def _kind_cell(loadout: LoadoutDef, kind: str, repo_root: Path) -> str:
    items = [_item_from_src(src, kind, repo_root) for src in _srcs(loadout, kind)]
    return _html_list(items)


def _etc_cell(loadout: LoadoutDef, repo_root: Path) -> str:
    items = [_item_from_src(src, "hooks", repo_root) for src in _srcs(loadout, "hooks")]
    items.extend((tool.name, None) for tool in loadout.cli_tools)
    return _html_list(items)


def _srcs(loadout: LoadoutDef, kind: str) -> list[str]:
    return [entry["src"] for entry in getattr(loadout, kind) if isinstance(entry.get("src"), str)]


def _item_from_src(src: str, kind: str, repo_root: Path) -> tuple[str, str | None]:
    return _src_label(src), _primary_href(src, kind, repo_root)


def _src_label(src: str) -> str:
    path = Path(src)
    return path.stem if path.suffix else path.name


def _primary_href(src: str, kind: str, repo_root: Path) -> str:
    path = Path(src)
    if path.suffix:
        return path.as_posix()
    return _directory_href(path, kind, repo_root)


def _directory_href(path: Path, kind: str, repo_root: Path) -> str:
    if kind == "skills":
        return (path / "SKILL.md").as_posix()
    if kind == "mcps":
        return _first_existing(repo_root, path, ("README.md", "mcp.yaml"))
    if kind == "hooks":
        return _first_existing(repo_root, path, ("SOURCE.md", "hook.yaml"))
    if kind == "agents":
        return (path / f"{path.name}.md").as_posix()
    return path.as_posix()


def _first_existing(repo_root: Path, directory: Path, names: tuple[str, ...]) -> str:
    for name in names:
        relative = directory / name
        if (repo_root / relative).is_file():
            return relative.as_posix()
    return (directory / names[-1]).as_posix()


def _html_list(items: list[tuple[str, str | None]]) -> str:
    # GFM table cells do not render nested markdown lists; use a single-line HTML
    # <ul> so GitHub shows bullets. CLI tools omit href by passing None.
    if not items:
        return EM_DASH
    return "<ul>" + "".join(_html_item(item) for item in items) + "</ul>"


def _html_item(item: tuple[str, str | None]) -> str:
    name, href = item
    label = f"<code>{name}</code>"
    if href is None:
        return f"<li>{label}</li>"
    return f'<li><a href="{href}">{label}</a></li>'


def _git_version_tags(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "tag", "--sort=-v:refname"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _pyproject_tag(repo_root: Path) -> str:
    path = repo_root / "pyproject.toml"
    if not path.is_file():
        return FALLBACK_TAG
    match = PYPROJECT_VERSION_RE.search(path.read_text())
    if match is None:
        return FALLBACK_TAG
    version = match.group(1)
    return version if version.startswith("v") else f"v{version}"


def _replace_block(text: str, start: str, end: str, body: str) -> str:
    start_at = text.find(start)
    end_at = text.find(end)
    if start_at == -1 or end_at == -1 or end_at < start_at:
        raise ValueError(f"template missing markers {start} / {end}")
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
    try:
        generate_readme(repo_root=args.repo_root, template=args.template, output=args.output)
    except ValueError as err:
        raise SystemExit(str(err)) from err


if __name__ == "__main__":
    main()
