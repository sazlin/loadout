"""`loadout` command-line entry points (spec 6)."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import click
import yaml

from loadout import __version__
from loadout.errors import LoadoutError, ValidationError
from loadout.fetch import fetch_source
from loadout.lint import lint_repo
from loadout.models import load_lockfile, load_manifest
from loadout.resolve import resolve_selection
from loadout.sync import LOCKFILE_NAME, MANIFEST_NAME
from loadout.sync import sync as run_sync
from loadout.update import update as run_update
from loadout.validate import validate_resolved

# No tagged release exists yet. `main` tracks the loadout repo's default branch; once a
# release is cut, generated manifests should default to pinning a `vX.Y.Z` tag instead.
DEFAULT_SOURCE = "https://github.com/sazlin/loadout"
DEFAULT_REF = "main"


@click.group()
@click.version_option(__version__, prog_name="loadout")
def main() -> None:
    """Centralized, versioned Cursor rules, skills, agents, hooks, and MCPs."""


@main.command()
@click.option("--check", is_flag=True, help="Report drift without writing.")
def sync(check: bool) -> None:
    """Apply the pinned loadout to this project, or check it for drift."""
    _guarded(lambda: run_sync(Path.cwd(), check=check))


@main.command()
@click.option("--loadouts", required=True, help="Comma-separated loadout names.")
@click.option("--source", default=DEFAULT_SOURCE, show_default=True, help="Loadout repo URL.")
@click.option("--ref", default=DEFAULT_REF, show_default=True, help="Git ref to pin.")
def init(loadouts: str, source: str, ref: str) -> None:
    """Write a starter .loadout.yaml manifest."""
    _guarded(lambda: _write_manifest(loadouts, source, ref))


@main.command()
@click.option("--to", "to_ref", default=None, help="Ref to update to. Defaults to the latest tag.")
def update(to_ref: str | None) -> None:
    """Bump the pinned ref, re-sync, and print the CHANGELOG entries that landed."""
    _guarded(lambda: run_update(Path.cwd(), to_ref=to_ref))


@main.command()
@click.option(
    "--list",
    "show_list",
    is_flag=True,
    required=True,
    help="Print the resolved src -> dest table.",
)
def resolve(show_list: bool) -> None:
    """Resolve the project's manifest and print what it selects."""
    del show_list  # the only supported view today; the flag exists for justfile parity
    _guarded(_print_resolved)


@main.command()
def lint() -> None:
    """Validate this loadout repo's rules, skills, hooks, agents, mcps, cli_tools, and loadouts (spec 7.1)."""
    _guarded(_run_lint)


def _guarded(action: Callable[[], object]) -> None:
    try:
        action()
    except LoadoutError as error:
        click.echo(f"loadout: error: {error}", err=True)
        sys.exit(error.code)


def _write_manifest(loadouts: str, source: str, ref: str) -> None:
    manifest_path = Path.cwd() / MANIFEST_NAME
    if manifest_path.exists():
        raise ValidationError(f"{MANIFEST_NAME} already exists; remove it first")

    names = _parse_loadout_names(loadouts)

    body = {"source": source, "ref": ref, "loadouts": names}
    manifest_path.write_text(yaml.safe_dump(body, sort_keys=False))
    click.echo(f"loadout: wrote {MANIFEST_NAME}")


def _parse_loadout_names(raw: str) -> list[str]:
    """Split a comma-separated --loadouts value into names."""
    names = [name.strip() for name in raw.split(",") if name.strip()]
    if not names:
        raise ValidationError("--loadouts requires at least one non-empty name")
    return names


def _print_resolved() -> None:
    project_root = Path.cwd()
    manifest_path = project_root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ValidationError(f"No {MANIFEST_NAME} found in {project_root}")

    manifest = load_manifest(manifest_path)
    lock = load_lockfile(project_root / LOCKFILE_NAME)
    fetched = fetch_source(manifest, lock)
    files, cli_tools = resolve_selection(manifest, fetched.root)
    validate_resolved(files, fetched.root, manifest.skills_dir, manifest.hooks_dir, manifest.agents_dir)

    for file in sorted(files, key=lambda resolved: resolved.dest):
        if file.kind == "mcp":
            click.echo(f"{file.src} -> .cursor/mcp.json, .mcp.json")
        else:
            click.echo(f"{file.src} -> {file.dest}")
    for tool in cli_tools:
        click.echo(f"cli_tools: {tool.name}: {tool.command}")


def _run_lint() -> None:
    result = lint_repo(Path.cwd())
    for warning in result.warnings:
        click.echo(f"loadout: warning: {warning}")
    for error in result.errors:
        click.echo(f"loadout: error: {error}", err=True)
    if not result.ok:
        sys.exit(2)
