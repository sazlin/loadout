from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from loadout.errors import ValidationError
from loadout.models import LoadoutDef, Manifest, load_loadout


@dataclass(frozen=True)
class ResolvedFile:
    src: str
    dest: str
    kind: Literal["rule", "skill_file"]


def resolve(manifest: Manifest, source_root: Path) -> list[ResolvedFile]:
    """Resolve manifest-selected loadouts into individual source and destination files."""
    loadouts = _load_selected_loadouts(manifest.loadouts, source_root)
    files = [
        resolved
        for loadout in loadouts
        for resolved in _resolve_loadout(loadout, manifest.skills_dir, source_root)
    ]
    files.extend(_resolve_includes(manifest, source_root))
    _validate_selectors(manifest.exclude, source_root)
    files = _apply_excludes(files, manifest.exclude)
    return _deduplicate(files)


def _load_selected_loadouts(names: list[str], source_root: Path) -> list[LoadoutDef]:
    loaded: dict[str, LoadoutDef] = {}
    visiting: set[str] = set()
    resolved: list[LoadoutDef] = []

    def visit(name: str) -> None:
        if name in loaded:
            return
        if name in visiting:
            raise ValidationError(f"Loadout extends cycle detected at {name!r}")

        path = source_root / "loadouts" / f"{name}.yaml"
        if not path.is_file():
            raise ValidationError(f"Loadout not found: {name}")

        visiting.add(name)
        loadout = load_loadout(path)
        for parent in loadout.extends:
            visit(parent)
        visiting.remove(name)
        loaded[name] = loadout
        resolved.append(loadout)

    for name in names:
        visit(name)
    return resolved


def _resolve_loadout(
    loadout: LoadoutDef, skills_dir: str, source_root: Path
) -> list[ResolvedFile]:
    rules = [
        ResolvedFile(
            src=src,
            dest=_entry_dest(entry, _default_rule_dest(src)),
            kind="rule",
        )
        for entry in loadout.rules
        for src in [_entry_src(entry)]
    ]
    skills = [
        resolved
        for entry in loadout.skills
        for src in [_entry_src(entry)]
        for resolved in _expand_skill(
            source_root,
            src,
            _entry_dest(entry, _default_skill_dest(skills_dir, src)),
        )
    ]
    return [*rules, *skills]


def _resolve_includes(manifest: Manifest, source_root: Path) -> list[ResolvedFile]:
    _validate_selectors(manifest.include, source_root)
    files: list[ResolvedFile] = []
    for src in manifest.include:
        path = source_root / src
        if path.is_file():
            files.append(ResolvedFile(src, _default_rule_dest(src), "rule"))
        else:
            files.extend(_expand_skill(source_root, src, _default_skill_dest(manifest.skills_dir, src)))
    return files


def _entry_src(entry: object) -> str:
    if not isinstance(entry, dict):
        raise ValidationError("Loadout entry must be a mapping")
    src = entry.get("src")
    if not isinstance(src, str) or not src:
        raise ValidationError("Loadout entry requires non-empty src")
    return src


def _entry_dest(entry: object, default: str) -> str:
    if not isinstance(entry, dict):
        raise ValidationError("Loadout entry must be a mapping")
    dest = entry.get("dest", default)
    if not isinstance(dest, str) or not dest:
        raise ValidationError("Loadout entry dest must be a non-empty string")
    return dest


def _default_rule_dest(src: str) -> str:
    return (PurePosixPath(".cursor/rules") / PurePosixPath(src).name).as_posix()


def _default_skill_dest(skills_dir: str, src: str) -> str:
    return (PurePosixPath(skills_dir) / PurePosixPath(src).name).as_posix()


def _expand_skill(source_root: Path, src: str, dest: str) -> list[ResolvedFile]:
    source = source_root / src
    if not source.is_dir():
        return []
    if PurePosixPath(dest).name != PurePosixPath(src).name:
        raise ValidationError(f"Skill destination must end with {PurePosixPath(src).name}: {dest}")

    files: list[ResolvedFile] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or _is_skipped_skill_file(path, source):
            continue
        relative = path.relative_to(source)
        files.append(
            ResolvedFile(
                src=path.relative_to(source_root).as_posix(),
                dest=(PurePosixPath(dest) / relative.as_posix()).as_posix(),
                kind="skill_file",
            )
        )
    return files


def _is_skipped_skill_file(path: Path, skill_root: Path) -> bool:
    relative_parts = path.relative_to(skill_root).parts
    if relative_parts[0] == "evals":
        return True
    return (
        "__pycache__" in relative_parts
        or "node_modules" in relative_parts
        or path.name.endswith(".pyc")
        or path.name == ".DS_Store"
    )


def _validate_selectors(selectors: list[str], source_root: Path) -> None:
    for selector in selectors:
        if not (source_root / selector).exists():
            raise ValidationError(f"Selector does not match a source path: {selector}")


def _apply_excludes(
    files: list[ResolvedFile], excludes: list[str]
) -> list[ResolvedFile]:
    return [
        file
        for file in files
        if not any(file.src == exclude or file.src.startswith(f"{exclude}/") for exclude in excludes)
    ]


def _deduplicate(files: list[ResolvedFile]) -> list[ResolvedFile]:
    seen: set[tuple[str, str]] = set()
    deduplicated: list[ResolvedFile] = []
    for file in files:
        key = (file.src, file.dest)
        if key not in seen:
            seen.add(key)
            deduplicated.append(file)
    return deduplicated
