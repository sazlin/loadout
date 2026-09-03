"""Bump the pinned ref, re-sync, and surface what changed upstream (spec 6, `loadout update`)."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loadout.errors import FetchError, LoadoutError, ValidationError
from loadout.fetch import fetch_source
from loadout.models import Manifest, load_lockfile, load_manifest
from loadout.sync import LOCKFILE_NAME, MANIFEST_NAME
from loadout.sync import sync as run_sync

_REF_LINE_RE = re.compile(r"^ref:.*$", re.MULTILINE)
_VERSION_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class UpdateResult:
    old_ref: str
    new_ref: str
    changelog: str


def update(project_root: Path, *, to_ref: str | None = None) -> UpdateResult:
    """Rewrite `.loadout.yaml`'s ref, sync, and report the CHANGELOG entries it pulled in."""
    manifest_path = project_root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ValidationError(f"No {MANIFEST_NAME} found in {project_root}")

    manifest = load_manifest(manifest_path)
    old_ref = manifest.ref
    new_ref = to_ref or _latest_tag(manifest.source)
    previous_source = _locked_source_for_same_ref(project_root, manifest, new_ref)

    original_manifest = manifest_path.read_text()
    _rewrite_ref(manifest_path, new_ref)
    try:
        run_sync(project_root)
    except LoadoutError:
        manifest_path.write_text(original_manifest)
        raise

    updated_manifest = load_manifest(manifest_path)
    lock = load_lockfile(project_root / LOCKFILE_NAME)
    if lock is None:
        raise ValidationError(f"No {LOCKFILE_NAME} written by sync")
    fetched = fetch_source(updated_manifest, resolved_sha=lock.resolved_sha)
    changelog = (
        _changelog_since(previous_source, fetched.root)
        if previous_source is not None
        else _changelog_between(fetched.root, old_ref, new_ref)
    )

    result = UpdateResult(old_ref=old_ref, new_ref=new_ref, changelog=changelog)
    _print_summary(result)
    return result


def _locked_source_for_same_ref(project_root: Path, manifest: Manifest, new_ref: str) -> Path | None:
    if manifest.ref != new_ref:
        return None
    lock = load_lockfile(project_root / LOCKFILE_NAME)
    if lock is None or lock.source != manifest.source or lock.ref != manifest.ref:
        return None
    return fetch_source(manifest, resolved_sha=lock.resolved_sha).root


def _latest_tag(source: str) -> str:
    result = _run_git(["git", "ls-remote", "--tags", "--sort=-v:refname", source])
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 2 or fields[1].endswith("^{}"):
            continue
        ref = fields[1]
        if ref.startswith("refs/tags/"):
            return ref.removeprefix("refs/tags/")
    raise FetchError(f"No tags found at {source!r}")


def _run_git(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, text=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as error:
        stderr = getattr(error, "stderr", None)
        detail = stderr.strip() if isinstance(stderr, str) and stderr.strip() else str(error)
        raise FetchError(f"Git command failed: {detail}") from error


def _rewrite_ref(manifest_path: Path, new_ref: str) -> None:
    text = manifest_path.read_text()
    if not _REF_LINE_RE.search(text):
        raise ValidationError(f"{manifest_path.name} has no ref: line to update")
    manifest_path.write_text(_REF_LINE_RE.sub(f"ref: {new_ref}", text, count=1))


def _changelog_since(previous_source: Path, current_source: Path) -> str:
    previous_path = previous_source / "CHANGELOG.md"
    current_path = current_source / "CHANGELOG.md"
    if not current_path.is_file():
        return ""
    previous_text = previous_path.read_text() if previous_path.is_file() else ""
    previous_sections = dict(_parse_sections(previous_text))
    changed_sections = [
        section
        for version, section in _parse_sections(current_path.read_text())
        if previous_sections.get(version) != section
    ]
    return "\n\n".join(changed_sections)


def _changelog_between(source_root: Path, old_ref: str, new_ref: str) -> str:
    changelog_path = source_root / "CHANGELOG.md"
    if not changelog_path.is_file():
        return ""
    return _slice_sections(changelog_path.read_text(), old_ref, new_ref)


def _slice_sections(text: str, old_ref: str, new_ref: str) -> str:
    """Return the `## <version>` sections newer than `old_ref` up to and including `new_ref`.

    Assumes newest-first ordering, matching Keep a Changelog convention and this repo's
    `CHANGELOG.md`.
    """
    sections = _parse_sections(text)
    versions = [version for version, _ in sections]
    new_version = _normalize_version(new_ref)
    old_version = _normalize_version(old_ref)

    if new_version not in versions:
        return ""

    new_index = versions.index(new_version)
    old_index = versions.index(old_version) if old_version in versions else len(sections)
    if old_index <= new_index:
        return ""

    return "\n\n".join(section for _, section in sections[new_index:old_index])


def _parse_sections(text: str) -> list[tuple[str, str]]:
    matches = list(_VERSION_HEADING_RE.finditer(text))
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        version = _normalize_version(match.group(1).strip())
        section_text = text[match.start() : end].rstrip("\n")
        sections.append((version, section_text))
    return sections


def _normalize_version(ref: str) -> str:
    if len(ref) > 1 and ref[0] in "vV" and ref[1].isdigit():
        return ref[1:]
    return ref


def _print_summary(result: UpdateResult) -> None:
    print(f"loadout: updated ref {result.old_ref} -> {result.new_ref}")
    if result.changelog:
        print()
        print(result.changelog)
