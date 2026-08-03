"""Materialize a resolved loadout into a project, or check the project for drift."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal, Never

from loadout import __version__
from loadout.blocks import (
    AGENT_RULES_BEGIN,
    AGENT_RULES_END,
    CLAUDE_IMPORT_BEGIN,
    CLAUDE_IMPORT_END,
    RuleIndexRow,
    render_agent_rules_block,
    render_claude_import_block,
    splice_block,
)
from loadout.errors import DriftError, ValidationError
from loadout.fetch import fetch_source
from loadout.frontmatter import parse_rule
from loadout.headers import inject_header
from loadout.io import atomic_write, sha256_bytes
from loadout.models import (
    FileEntry,
    Lockfile,
    ManagedBlock,
    Manifest,
    dump_lockfile,
    load_lockfile,
    load_manifest,
)
from loadout.resolve import ResolvedFile, resolve
from loadout.validate import validate_resolved

_BlockName = Literal["agent-rules", "agents-import"]

MANIFEST_NAME = ".loadout.yaml"
LOCKFILE_NAME = ".loadout.lock"
LOCKFILE_VERSION = 1
AGENTS_FILE = "AGENTS.md"
AGENTS_BLOCK: _BlockName = "agent-rules"
AGENTS_HEADING = "# Agent Instructions\n"
CLAUDE_FILE = "CLAUDE.md"
CLAUDE_BLOCK: _BlockName = "agents-import"
EXECUTABLE_MODE = 0o755
REGULAR_MODE = 0o644


@dataclass(frozen=True)
class SyncResult:
    added: int
    updated: int
    removed: int
    unchanged: int
    agents_changed: bool
    claude_changed: bool


@dataclass(frozen=True)
class _PlannedFile:
    dest: str
    src: str
    content: bytes
    executable: bool

    @property
    def sha256(self) -> str:
        return sha256_bytes(self.content)

    @property
    def mode(self) -> int:
        return EXECUTABLE_MODE if self.executable else REGULAR_MODE

    @property
    def lock_mode(self) -> str | None:
        return "755" if self.executable else None


@dataclass(frozen=True)
class _PlannedBlock:
    """A managed block's desired state, plus the whole file it lives in.

    ``text`` is None when the block should no longer appear in the file at all.
    """

    file: str
    block: _BlockName
    text: str | None
    content: bytes

    @property
    def sha256(self) -> str:
        if self.text is None:
            raise AssertionError(f"Removed block has no hash: {self.file}")
        return sha256_bytes(self.text.encode())


@dataclass(frozen=True)
class _Plan:
    manifest: Manifest
    resolved_sha: str
    files: list[_PlannedFile]
    blocks: list[_PlannedBlock]
    removed_blocks: list[_PlannedBlock]


def sync(project_root: Path, *, check: bool = False) -> SyncResult:
    """Sync a project against its manifest, or report drift without writing."""
    manifest_path = project_root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ValidationError(f"No {MANIFEST_NAME} found in {project_root}")

    manifest = load_manifest(manifest_path)
    lock_path = project_root / LOCKFILE_NAME
    lock = load_lockfile(lock_path)

    fetched = fetch_source(manifest, lock)
    resolved = resolve(manifest, fetched.root)
    validate_resolved(resolved, fetched.root, manifest.skills_dir)

    plan = _build_plan(manifest, fetched.root, fetched.resolved_sha, resolved, project_root)

    if check:
        return _check(project_root, plan, lock)
    return _apply(project_root, lock_path, plan, lock)


def _build_plan(
    manifest: Manifest,
    source_root: Path,
    resolved_sha: str,
    resolved: list[ResolvedFile],
    project_root: Path,
) -> _Plan:
    files = sorted(
        (_plan_file(file, source_root, resolved_sha) for file in resolved),
        key=lambda planned: planned.dest,
    )
    rows = [
        _rule_row(file, source_root) for file in sorted(resolved, key=lambda file: file.dest) if file.kind == "rule"
    ]
    blocks, removed_blocks = _plan_blocks(manifest, project_root, rows)
    return _Plan(
        manifest=manifest,
        resolved_sha=resolved_sha,
        files=files,
        blocks=blocks,
        removed_blocks=removed_blocks,
    )


def _plan_file(file: ResolvedFile, source_root: Path, resolved_sha: str) -> _PlannedFile:
    source_path = source_root / file.src
    raw = source_path.read_bytes()

    match file.kind:
        case "rule":
            content = inject_header(raw.decode(), file.src, resolved_sha).encode()
            executable = False
        case "skill_file":
            relative = _skill_relative_parts(file.src)
            if relative == ("SKILL.md",):
                content = inject_header(raw.decode(), file.src, resolved_sha).encode()
            else:
                content = raw
            executable = relative[0] == "scripts" or _is_executable(source_path)
        case _:
            _exhaustive: Never = file.kind
            raise AssertionError(f"Unhandled file kind: {file.kind!r}")

    return _PlannedFile(dest=file.dest, src=file.src, content=content, executable=executable)


def _skill_relative_parts(src: str) -> tuple[str, ...]:
    parts = PurePosixPath(src).parts
    try:
        skills_index = parts.index("skills")
    except ValueError as error:
        raise ValidationError(f"Skill source must be under skills/: {src}") from error
    relative = parts[skills_index + 2 :]
    if not relative:
        raise ValidationError(f"Skill source must name a file inside the skill: {src}")
    return relative


def _is_executable(path: Path) -> bool:
    return bool(path.stat().st_mode & 0o111)


def _rule_row(file: ResolvedFile, source_root: Path) -> RuleIndexRow:
    source_path = source_root / file.src
    meta = parse_rule(source_path, source_path.read_text())
    return RuleIndexRow(
        path=file.dest,
        scope=_scope(meta.always_apply, meta.globs),
        description=meta.description,
    )


def _scope(always_apply: bool, globs: list[str] | None) -> str:
    if always_apply:
        return "Always"
    if globs:
        return ", ".join(f"`{glob}`" for glob in globs)
    return "On request"


def _plan_blocks(
    manifest: Manifest, project_root: Path, rows: list[RuleIndexRow]
) -> tuple[list[_PlannedBlock], list[_PlannedBlock]]:
    planned = [
        _plan_block(
            project_root,
            AGENTS_FILE,
            AGENTS_BLOCK,
            render_agent_rules_block(rows),
            placement="append",
            heading=AGENTS_HEADING,
        ),
        # Planned even when the bridge is off, so turning it off removes a block an
        # earlier sync wrote. `_plan_block` returns None when there is no CLAUDE.md.
        _plan_block(
            project_root,
            CLAUDE_FILE,
            CLAUDE_BLOCK,
            render_claude_import_block() if manifest.claude_bridge else None,
            placement="prepend",
        ),
    ]

    blocks = [block for block in planned if block is not None and block.text is not None]
    removed = [block for block in planned if block is not None and block.text is None]
    return blocks, removed


def _plan_block(
    project_root: Path,
    file_name: str,
    block_name: _BlockName,
    rendered: str | None,
    *,
    placement: Literal["append", "prepend"],
    heading: str = "",
) -> _PlannedBlock | None:
    """Plan the whole file around a managed block, or None when there is nothing to do."""
    path = project_root / file_name
    exists = path.is_file()
    if not exists and rendered is None:
        return None

    begin_marker, end_marker = _markers(block_name)
    current = path.read_text() if exists else heading
    spliced = splice_block(current, begin_marker, end_marker, rendered, placement=placement)
    return _PlannedBlock(
        file=file_name,
        block=block_name,
        text=rendered,
        content=_ensure_trailing_newline(spliced).encode(),
    )


def _ensure_trailing_newline(text: str) -> str:
    if not text or text.endswith("\n"):
        return text
    return f"{text}\n"


def _apply(project_root: Path, lock_path: Path, plan: _Plan, lock: Lockfile | None) -> SyncResult:
    removed = _prune(project_root, plan, lock)

    counts = {"added": 0, "updated": 0, "unchanged": 0}
    for planned in plan.files:
        counts[_write_file(project_root / planned.dest, planned)] += 1

    changed_blocks = {
        block.file: _write_bytes(project_root / block.file, block.content)
        for block in [*plan.blocks, *plan.removed_blocks]
    }

    _write_lockfile(lock_path, plan, lock)

    result = SyncResult(
        added=counts["added"],
        updated=counts["updated"],
        removed=removed,
        unchanged=counts["unchanged"],
        agents_changed=changed_blocks.get(AGENTS_FILE, False),
        claude_changed=changed_blocks.get(CLAUDE_FILE, False),
    )
    _print_summary(result)
    return result


def _write_file(path: Path, planned: _PlannedFile) -> Literal["added", "updated", "unchanged"]:
    if not path.exists():
        atomic_write(path, planned.content, planned.mode)
        return "added"
    if path.read_bytes() == planned.content and _is_executable(path) == planned.executable:
        return "unchanged"
    atomic_write(path, planned.content, planned.mode)
    return "updated"


def _write_bytes(path: Path, content: bytes) -> bool:
    if path.exists() and path.read_bytes() == content:
        return False
    atomic_write(path, content, REGULAR_MODE)
    return True


def _prune(project_root: Path, plan: _Plan, lock: Lockfile | None) -> int:
    if lock is None:
        return 0

    planned_dests = {planned.dest for planned in plan.files}
    removed = 0
    for entry in lock.files:
        if entry.dest in planned_dests:
            continue
        path = project_root / entry.dest
        if not _is_inside(project_root, path):
            continue
        if path.is_file():
            path.unlink()
            removed += 1
            _prune_empty_parents(project_root, path.parent)
    return removed


def _prune_empty_parents(project_root: Path, directory: Path) -> None:
    current = directory
    while (
        current != project_root
        and _is_inside(project_root, current)
        and current.is_dir()
        and not any(current.iterdir())
    ):
        current.rmdir()
        current = current.parent


def _is_inside(project_root: Path, path: Path) -> bool:
    """Guard against a hand-edited lockfile pointing outside the project.

    Both sides are resolved first: ``relative_to`` is purely lexical, so it happily
    accepts ``project/../elsewhere``.
    """
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return False
    return True


def _write_lockfile(lock_path: Path, plan: _Plan, lock: Lockfile | None) -> None:
    new_lock = _build_lockfile(plan, _synced_at())
    if lock is not None and _lock_matches(lock, new_lock):
        return
    dump_lockfile(lock_path, new_lock)


def _build_lockfile(plan: _Plan, synced_at: str) -> Lockfile:
    return Lockfile(
        lockfile_version=LOCKFILE_VERSION,
        source=plan.manifest.source,
        ref=plan.manifest.ref,
        resolved_sha=plan.resolved_sha,
        synced_at=synced_at,
        tool_version=__version__,
        files=[
            FileEntry(
                dest=planned.dest,
                src=planned.src,
                sha256=planned.sha256,
                mode=planned.lock_mode,
            )
            for planned in plan.files
        ],
        managed_blocks=[ManagedBlock(file=block.file, block=block.block, sha256=block.sha256) for block in plan.blocks],
    )


def _lock_matches(lock: Lockfile, new_lock: Lockfile) -> bool:
    """Compare everything but ``synced_at`` so an unchanged sync leaves no diff."""
    return (
        lock.lockfile_version == new_lock.lockfile_version
        and lock.source == new_lock.source
        and lock.ref == new_lock.ref
        and lock.resolved_sha == new_lock.resolved_sha
        and lock.tool_version == new_lock.tool_version
        and lock.files == new_lock.files
        and lock.managed_blocks == new_lock.managed_blocks
    )


def _synced_at() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _print_summary(result: SyncResult) -> None:
    print(
        f"loadout: {result.added} added, {result.updated} updated, "
        f"{result.removed} removed, {result.unchanged} unchanged"
    )
    for file_name, changed in (
        (AGENTS_FILE, result.agents_changed),
        (CLAUDE_FILE, result.claude_changed),
    ):
        print(f"loadout: {file_name} block {'updated' if changed else 'unchanged'}")
    if _changed_anything(result):
        print("loadout: reload the Cursor window and restart Claude Code to pick this up")


def _changed_anything(result: SyncResult) -> bool:
    return bool(result.added or result.updated or result.removed or result.agents_changed or result.claude_changed)


def _check(project_root: Path, plan: _Plan, lock: Lockfile | None) -> SyncResult:
    if lock is None:
        raise DriftError(f"No lockfile at {LOCKFILE_NAME}; run `loadout sync`")

    problems: list[str] = []
    problems.extend(_check_lock_identity(plan, lock))
    problems.extend(_check_files(project_root, plan, lock))
    problems.extend(_check_blocks(project_root, plan, lock))

    if problems:
        raise DriftError("\n".join(["Loadout drift detected:", *problems]))

    return SyncResult(
        added=0,
        updated=0,
        removed=0,
        unchanged=len(plan.files),
        agents_changed=False,
        claude_changed=False,
    )


def _check_lock_identity(plan: _Plan, lock: Lockfile) -> list[str]:
    problems: list[str] = []
    if lock.source != plan.manifest.source:
        problems.append(f"  source: lockfile has {lock.source}, manifest has {plan.manifest.source}")
    if lock.ref != plan.manifest.ref:
        problems.append(f"  ref: lockfile has {lock.ref}, manifest has {plan.manifest.ref}")
    if lock.resolved_sha != plan.resolved_sha:
        message = f"resolved_sha: lockfile has {lock.resolved_sha}, source resolved to {plan.resolved_sha}"
        if "local" in (lock.resolved_sha, plan.resolved_sha):
            print(f"loadout: warning: {message}")
        else:
            problems.append(f"  {message}")
    return problems


def _check_files(project_root: Path, plan: _Plan, lock: Lockfile) -> list[str]:
    problems: list[str] = []
    locked = {entry.dest: entry for entry in lock.files}
    planned = {file.dest: file for file in plan.files}

    for dest in sorted(set(locked) - set(planned)):
        problems.append(f"  {dest}: present in lockfile but no longer selected")

    for dest, file in planned.items():
        entry = locked.get(dest)
        if entry is None:
            problems.append(f"  {dest}: selected but missing from the lockfile")
            continue
        if entry.sha256 != file.sha256 or entry.mode != file.lock_mode:
            problems.append(f"  {dest}: lockfile entry is stale")
            continue

        path = project_root / dest
        if not path.is_file():
            problems.append(f"  {dest}: missing from the project")
            continue
        if sha256_bytes(path.read_bytes()) != file.sha256:
            problems.append(f"  {dest}: content differs from the lockfile hash")
        elif entry.mode == "755" and not _is_executable(path):
            problems.append(f"  {dest}: expected mode 755")

    return sorted(problems)


def _check_blocks(project_root: Path, plan: _Plan, lock: Lockfile) -> list[str]:
    problems: list[str] = []
    locked = {block.file: block for block in lock.managed_blocks}
    planned = {block.file: block for block in plan.blocks}

    for file_name in sorted(set(locked) - set(planned)):
        problems.append(f"  {file_name}: managed block is no longer expected")

    for file_name, block in planned.items():
        entry = locked.get(file_name)
        if entry is None or entry.sha256 != block.sha256:
            problems.append(f"  {file_name}: managed block differs from the lockfile")
            continue
        on_disk = _read_block(project_root / file_name, block)
        if on_disk is None:
            problems.append(f"  {file_name}: managed block is missing")
        elif sha256_bytes(on_disk.encode()) != block.sha256:
            problems.append(f"  {file_name}: managed block on disk was edited")

    for block in plan.removed_blocks:
        if _read_block(project_root / block.file, block) is not None:
            problems.append(f"  {block.file}: managed block should have been removed")

    return sorted(problems)


def _read_block(path: Path, block: _PlannedBlock) -> str | None:
    """Extract the marked span from disk.

    Mangled markers already aborted while the plan was built, since planning splices the
    same file.
    """
    if not path.is_file():
        return None
    begin, end = _markers(block.block)
    text = path.read_text()
    if begin not in text or end not in text:
        return None
    begin_index = text.index(begin)
    end_index = text.index(end) + len(end)
    return text[begin_index:end_index]


def _markers(block_name: _BlockName) -> tuple[str, str]:
    match block_name:
        case "agent-rules":
            return AGENT_RULES_BEGIN, AGENT_RULES_END
        case "agents-import":
            return CLAUDE_IMPORT_BEGIN, CLAUDE_IMPORT_END
        case _:
            _exhaustive: Never = block_name
            raise AssertionError(f"Unhandled managed block: {block_name!r}")
