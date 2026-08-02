from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from loadout.errors import FetchError, ValidationError
from loadout.models import Lockfile, Manifest


@dataclass(frozen=True)
class FetchedSource:
    root: Path
    resolved_sha: str
    from_local: bool


def fetch_source(
    manifest: Manifest,
    lock: Lockfile | None,
    *,
    env: Mapping[str, str] = os.environ,
) -> FetchedSource:
    local_path = env.get("LOADOUT_PATH")
    if local_path:
        root = Path(local_path).expanduser()
        if not root.is_dir():
            raise ValidationError(f"LOADOUT_PATH is not a directory: {root}")
        return FetchedSource(root=root.resolve(), resolved_sha="local", from_local=True)

    resolved_sha = _locked_sha(manifest, lock) or _resolve_sha(manifest)
    cache_root = _cache_root(env)
    destination = cache_root / resolved_sha
    if destination.is_dir():
        return FetchedSource(
            root=destination, resolved_sha=resolved_sha, from_local=False
        )
    if destination.exists():
        raise FetchError(f"Source cache path is not a directory: {destination}")

    _clone_to_cache(manifest.source, resolved_sha, cache_root, destination)
    return FetchedSource(root=destination, resolved_sha=resolved_sha, from_local=False)


def _locked_sha(manifest: Manifest, lock: Lockfile | None) -> str | None:
    if lock is not None and lock.ref == manifest.ref:
        return lock.resolved_sha
    return None


def _cache_root(env: Mapping[str, str]) -> Path:
    cache_home = env.get("XDG_CACHE_HOME")
    if cache_home:
        return Path(cache_home).expanduser() / "loadout" / "sources"
    return Path.home() / ".cache" / "loadout" / "sources"


def _resolve_sha(manifest: Manifest) -> str:
    result = _run_git(["git", "ls-remote", manifest.source, manifest.ref])
    line = result.stdout.strip().splitlines()
    if not line:
        raise FetchError(
            f"Could not resolve ref {manifest.ref!r} from {manifest.source!r}"
        )
    resolved_sha = line[0].split(maxsplit=1)[0]
    if not resolved_sha:
        raise FetchError(
            f"Could not resolve ref {manifest.ref!r} from {manifest.source!r}"
        )
    return resolved_sha


def _clone_to_cache(
    source: str, resolved_sha: str, cache_root: Path, destination: Path
) -> None:
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache_root) as temp_dir:
            checkout = Path(temp_dir) / "checkout"
            _run_git(["git", "clone", "--depth", "1", "--no-checkout", source, str(checkout)])
            _run_git(
                [
                    "git",
                    "-C",
                    str(checkout),
                    "fetch",
                    "--depth",
                    "1",
                    "origin",
                    resolved_sha,
                ]
            )
            _run_git(["git", "-C", str(checkout), "checkout", "--detach", resolved_sha])
            if destination.exists():
                return
            shutil.move(str(checkout), destination)
    except OSError as error:
        raise FetchError(f"Could not cache source from {source!r}: {error}") from error


def _run_git(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, text=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as error:
        stderr = getattr(error, "stderr", None)
        detail = stderr.strip() if isinstance(stderr, str) and stderr.strip() else str(error)
        raise FetchError(f"Git command failed: {detail}") from error
