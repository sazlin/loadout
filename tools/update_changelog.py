#!/usr/bin/env python3
"""Update CHANGELOG.md when the Loadout package version changes.

Detects the current version from pyproject.toml, finds the commit that last
changed the version, summarizes commits since then, and inserts a new
CHANGELOG section when one is missing.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
INIT_PY = ROOT / "src" / "loadout" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"

VERSION_HEADING_RE = re.compile(r"^##\s+(\d+\.\d+\.\d+)\s*$", re.MULTILINE)
INIT_VERSION_RE = re.compile(r'^__version__\s*=\s*"(\d+\.\d+\.\d+)"\s*$', re.MULTILINE)
SKIP_COMMIT_RE = re.compile(
    r"^(?:"
    r"chore(?:\(.+\))?:"
    r"|ci(?:\(.+\))?:"
    r"|test(?:\(.+\))?:"
    r"|docs(?:\(.+\))?:"
    r"|style(?:\(.+\))?:"
    r"|merge "
    r"|bump version"
    r"|update changelog"
    r")",
    re.IGNORECASE,
)


class ChangelogError(RuntimeError):
    pass


def run_git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise ChangelogError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def read_pyproject_version(text: str) -> str:
    data = tomllib.loads(text)
    try:
        version = data["project"]["version"]
    except KeyError as exc:
        raise ChangelogError("pyproject.toml missing [project].version") from exc
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ChangelogError(f"unsupported version value: {version!r}")
    return version


def read_init_version(text: str) -> str | None:
    match = INIT_VERSION_RE.search(text)
    return match.group(1) if match else None


def current_version() -> str:
    return read_pyproject_version(PYPROJECT.read_text(encoding="utf-8"))


def ensure_init_version_matches(version: str) -> None:
    init_version = read_init_version(INIT_PY.read_text(encoding="utf-8"))
    if init_version is None:
        raise ChangelogError(f"{INIT_PY.relative_to(ROOT)} missing __version__")
    if init_version != version:
        raise ChangelogError(
            f"version mismatch: pyproject.toml={version} "
            f"__init__.py={init_version}"
        )


def version_at_revision(revision: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:pyproject.toml"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return read_pyproject_version(result.stdout)
    except ChangelogError:
        return None


def find_previous_version_boundary(version: str) -> tuple[str | None, str | None]:
    """Return (previous_version, boundary_commit).

    boundary_commit is the newest commit where pyproject.toml still had a
    different version (or None if this is the first versioned commit).
    """
    history = run_git(
        "log",
        "--format=%H",
        "--",
        "pyproject.toml",
    ).splitlines()
    for sha in history:
        older = version_at_revision(sha)
        if older is None:
            continue
        if older != version:
            return older, sha
    return None, None


def collect_commit_subjects(since_exclusive: str | None) -> list[str]:
    args = ["log", "--format=%s"]
    if since_exclusive:
        args.append(f"{since_exclusive}..HEAD")
    else:
        args.append("HEAD")
    subjects = [line.strip() for line in run_git(*args).splitlines() if line.strip()]
    return subjects


def normalize_subject(subject: str) -> str | None:
    cleaned = subject.strip()
    if not cleaned or SKIP_COMMIT_RE.match(cleaned):
        return None
    # Drop conventional-commit prefixes for readability.
    cleaned = re.sub(
        r"^(feat|fix|perf|refactor|revert)(\(.+\))?:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    if cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    if cleaned.endswith("."):
        cleaned = cleaned[:-1]
    return cleaned


def summarize_changes(subjects: list[str]) -> list[str]:
    bullets: list[str] = []
    seen: set[str] = set()
    for subject in subjects:
        bullet = normalize_subject(subject)
        if bullet is None:
            continue
        key = bullet.casefold()
        if key in seen:
            continue
        seen.add(key)
        bullets.append(bullet)
    return bullets


def changelog_has_version(text: str, version: str) -> bool:
    return any(match.group(1) == version for match in VERSION_HEADING_RE.finditer(text))


def render_entry(version: str, bullets: list[str]) -> str:
    lines = [f"## {version}", ""]
    if bullets:
        lines.extend(f"- {bullet}" for bullet in bullets)
    else:
        lines.append("- Version bump")
    lines.append("")
    return "\n".join(lines)


def insert_changelog_entry(text: str, version: str, bullets: list[str]) -> str:
    if changelog_has_version(text, version):
        return text

    entry = render_entry(version, bullets).rstrip("\n") + "\n"
    heading = re.search(r"^#\s+CHANGELOG[ \t]*$", text, re.MULTILINE)
    if heading:
        # Keep the heading line (including its trailing newline if present).
        line_end = text.find("\n", heading.start())
        prefix = text[: line_end + 1] if line_end != -1 else text[: heading.end()] + "\n"
        rest = text[len(prefix) :].lstrip("\n")
        if rest:
            if not rest.endswith("\n"):
                rest += "\n"
            return f"{prefix}\n{entry}\n{rest}"
        return f"{prefix}\n{entry}"

    body = text.lstrip("\n")
    if body:
        if not body.endswith("\n"):
            body += "\n"
        return f"# CHANGELOG\n\n{entry}\n{body}"
    return f"# CHANGELOG\n\n{entry}"

def update_changelog(*, dry_run: bool = False) -> dict[str, object]:
    version = current_version()
    ensure_init_version_matches(version)

    changelog_text = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else "# CHANGELOG\n"
    if changelog_has_version(changelog_text, version):
        return {
            "changed": False,
            "version": version,
            "reason": "changelog already has this version",
            "bullets": [],
        }

    previous_version, boundary = find_previous_version_boundary(version)
    subjects = collect_commit_subjects(boundary)
    bullets = summarize_changes(subjects)
    updated = insert_changelog_entry(changelog_text, version, bullets)

    if not dry_run:
        CHANGELOG.write_text(updated, encoding="utf-8")

    return {
        "changed": True,
        "version": version,
        "previous_version": previous_version,
        "boundary_commit": boundary,
        "bullets": bullets,
        "reason": "inserted changelog entry",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing CHANGELOG.md",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if CHANGELOG.md is missing an entry for the current version",
    )
    args = parser.parse_args(argv)

    try:
        if args.check:
            version = current_version()
            text = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else ""
            if changelog_has_version(text, version):
                print(f"CHANGELOG.md already includes {version}")
                return 0
            print(f"CHANGELOG.md is missing an entry for {version}", file=sys.stderr)
            return 1

        result = update_changelog(dry_run=args.dry_run)
    except ChangelogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"version={result['version']}")
    print(f"changed={result['changed']}")
    print(f"reason={result['reason']}")
    if result.get("previous_version"):
        print(f"previous_version={result['previous_version']}")
    for bullet in result.get("bullets", []):
        print(f"- {bullet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
