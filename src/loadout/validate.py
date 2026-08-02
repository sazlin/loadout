from __future__ import annotations

from pathlib import Path, PurePosixPath

from loadout.errors import ValidationError
from loadout.frontmatter import parse_rule, parse_skill_md
from loadout.resolve import ResolvedFile


def validate_resolved(
    files: list[ResolvedFile], source_root: Path, skills_dir: str
) -> None:
    """Validate resolved files before writing them to a target project."""
    destinations: dict[str, str] = {}
    skill_roots: dict[str, Path] = {}

    for file in files:
        source_path = source_root / file.src
        if not source_path.is_file():
            raise ValidationError(f"Resolved source file not found: {file.src}")

        existing_source = destinations.setdefault(file.dest, file.src)
        if existing_source != file.src:
            raise ValidationError(
                f"Destination collision at {file.dest}: "
                f"{existing_source} and {file.src}"
            )

        if file.kind == "rule":
            parse_rule(source_path, source_path.read_text())
        else:
            skill_root = _skill_root(file, source_root, skills_dir)
            skill_roots[skill_root.as_posix()] = skill_root

    for skill_root in skill_roots.values():
        skill_md = skill_root / "SKILL.md"
        if not skill_md.is_file():
            raise ValidationError(f"Skill is missing SKILL.md: {skill_root}")
        parse_skill_md(skill_md, skill_md.read_text(), dir_name=skill_root.name)


def _skill_root(file: ResolvedFile, source_root: Path, skills_dir: str) -> Path:
    source_parts = PurePosixPath(file.src).parts
    try:
        skills_index = source_parts.index("skills")
        source_dir_name = source_parts[skills_index + 1]
    except (ValueError, IndexError) as error:
        raise ValidationError(f"Skill source must be under skills/: {file.src}") from error

    try:
        destination_relative = PurePosixPath(file.dest).relative_to(
            PurePosixPath(skills_dir)
        )
        destination_dir_name = destination_relative.parts[0]
    except ValueError as error:
        raise ValidationError(
            f"Skill destination must be under {skills_dir}: {file.dest}"
        ) from error

    if source_dir_name != destination_dir_name:
        raise ValidationError(
            "Skill destination directory must match source directory: "
            f"{file.dest}"
        )

    return source_root.joinpath(*source_parts[: skills_index + 2])
