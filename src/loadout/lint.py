"""Validate a loadout repo's rules, skills, and loadouts (`loadout lint`, spec 7.1)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from loadout.errors import ValidationError
from loadout.frontmatter import parse_rule, parse_skill_md
from loadout.models import LoadoutDef, Manifest, load_loadout
from loadout.resolve import resolve
from loadout.validate import validate_resolved

SKILL_MD_WARN_LINES = 500
REFERENCE_WARN_LINES = 300
_TOC_HEADING_RE = re.compile(r"^#{1,6}\s*(table of contents|contents)\s*$", re.IGNORECASE)
_TOC_LIST_ITEM_RE = re.compile(r"^\s*[-*]\s+\[.+\]\(#")


@dataclass
class LintResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def lint_repo(repo_root: Path) -> LintResult:
    """Run every `just lint` check (spec 7.1) against a loadout repo.

    Tolerates missing `rules/`, `skills/`, or `loadouts/` directories so it can run
    cleanly against an empty or partially-built repo.
    """
    result = LintResult()
    _lint_rules(repo_root, result)
    _lint_skills(repo_root, result)
    rule_srcs, skill_srcs = _lint_loadouts(repo_root, result)
    _lint_orphans(repo_root, rule_srcs, skill_srcs, result)
    return result


def _lint_rules(repo_root: Path, result: LintResult) -> None:
    rules_dir = repo_root / "rules"
    if not rules_dir.is_dir():
        return

    for path in sorted(rules_dir.rglob("*.mdc")):
        relative = path.relative_to(repo_root).as_posix()
        try:
            meta = parse_rule(path, path.read_text())
        except ValidationError as error:
            result.errors.append(f"{relative}: {error}")
            continue
        if meta.always_apply and not relative.startswith("rules/core/"):
            result.errors.append(
                f"{relative}: alwaysApply: true is only allowed under rules/core/"
            )


def _lint_skills(repo_root: Path, result: LintResult) -> None:
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        return

    for skill_root in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
        _lint_skill(repo_root, skill_root, result)


def _lint_skill(repo_root: Path, skill_root: Path, result: LintResult) -> None:
    relative_root = skill_root.relative_to(repo_root).as_posix()
    skill_md = skill_root / "SKILL.md"
    if not skill_md.is_file():
        result.errors.append(f"{relative_root}: missing SKILL.md")
        return

    text = skill_md.read_text()
    try:
        parse_skill_md(skill_md, text, dir_name=skill_root.name)
    except ValidationError as error:
        result.errors.append(f"{relative_root}/SKILL.md: {error}")

    line_count = text.count("\n") + 1
    if line_count > SKILL_MD_WARN_LINES:
        result.warnings.append(
            f"{relative_root}/SKILL.md: {line_count} lines exceeds {SKILL_MD_WARN_LINES}; "
            "push detail into references/"
        )

    for stray in sorted(skill_root.rglob("SKILL.md")):
        if stray == skill_md:
            continue
        result.errors.append(
            f"{stray.relative_to(repo_root).as_posix()}: stray SKILL.md below skill root "
            f"{relative_root}; move it under references/ with a different filename"
        )

    _lint_evals(repo_root, skill_root, result)
    _lint_reference_lengths(repo_root, skill_root, result)


def _lint_evals(repo_root: Path, skill_root: Path, result: LintResult) -> None:
    evals_path = skill_root / "evals" / "evals.json"
    if not evals_path.is_file():
        return

    relative_evals = evals_path.relative_to(repo_root).as_posix()
    try:
        data = json.loads(evals_path.read_text())
    except json.JSONDecodeError as error:
        result.errors.append(f"{relative_evals}: invalid JSON: {error}")
        return

    evals = data.get("evals", []) if isinstance(data, dict) else []
    for index, entry in enumerate(evals):
        files = entry.get("files", []) if isinstance(entry, dict) else []
        for file_path in files:
            if not (skill_root / file_path).is_file():
                result.errors.append(
                    f"{relative_evals}: evals[{index}].files references missing path {file_path}"
                )


def _lint_reference_lengths(repo_root: Path, skill_root: Path, result: LintResult) -> None:
    references_dir = skill_root / "references"
    if not references_dir.is_dir():
        return

    for path in sorted(references_dir.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(errors="ignore")
        line_count = text.count("\n") + 1
        if line_count > REFERENCE_WARN_LINES and not _has_toc(text):
            relative = path.relative_to(repo_root).as_posix()
            result.warnings.append(
                f"{relative}: {line_count} lines exceeds {REFERENCE_WARN_LINES} "
                "without a table of contents"
            )


def _has_toc(text: str) -> bool:
    head_lines = text.splitlines()[:40]
    list_items = 0
    for line in head_lines:
        if _TOC_HEADING_RE.match(line.strip()):
            return True
        if _TOC_LIST_ITEM_RE.match(line):
            list_items += 1
    return list_items >= 3


def _lint_loadouts(repo_root: Path, result: LintResult) -> tuple[set[str], set[str]]:
    """Resolve every loadout and return the (rule src, skill src) sets it references."""
    loadouts_dir = repo_root / "loadouts"
    if not loadouts_dir.is_dir():
        return set(), set()

    names = sorted(path.stem for path in loadouts_dir.glob("*.yaml"))
    rule_srcs: set[str] = set()
    skill_srcs: set[str] = set()
    cache: dict[str, LoadoutDef] = {}

    def load(name: str) -> LoadoutDef:
        if name not in cache:
            cache[name] = load_loadout(loadouts_dir / f"{name}.yaml")
        return cache[name]

    def collect(name: str, chain: tuple[str, ...]) -> None:
        if name in chain:
            raise ValidationError(f"Loadout extends cycle detected at {name!r}")
        loadout = load(name)
        for parent in loadout.extends:
            collect(parent, (*chain, name))
        for entry in loadout.rules:
            src = entry.get("src")
            if isinstance(src, str):
                rule_srcs.add(src)
        for entry in loadout.skills:
            src = entry.get("src")
            if isinstance(src, str):
                skill_srcs.add(src)

    for name in names:
        try:
            collect(name, ())
        except ValidationError as error:
            result.errors.append(f"loadouts/{name}.yaml: {error}")
            continue

        try:
            manifest = Manifest(source="lint", ref="lint", loadouts=[name])
            resolved = resolve(manifest, repo_root)
            validate_resolved(resolved, repo_root, manifest.skills_dir)
        except ValidationError as error:
            result.errors.append(f"loadouts/{name}.yaml: {error}")

    return rule_srcs, skill_srcs


def _lint_orphans(
    repo_root: Path, rule_srcs: set[str], skill_srcs: set[str], result: LintResult
) -> None:
    rules_dir = repo_root / "rules"
    if rules_dir.is_dir():
        for path in sorted(rules_dir.rglob("*.mdc")):
            relative = path.relative_to(repo_root).as_posix()
            if relative not in rule_srcs:
                result.errors.append(f"{relative}: orphan rule, not referenced by any loadout")

    skills_dir = repo_root / "skills"
    if skills_dir.is_dir():
        for skill_root in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
            relative = skill_root.relative_to(repo_root).as_posix()
            if relative not in skill_srcs:
                result.errors.append(f"{relative}: orphan skill, not referenced by any loadout")
