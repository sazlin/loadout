from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from loadout.errors import FetchError, ValidationError
from loadout.models import Manifest

_DEFAULT_GIT_TIMEOUT_SECONDS = 120
_GIT_TIMEOUT_ENV = "LOADOUT_GIT_TIMEOUT_SECONDS"


@dataclass(frozen=True)
class FetchedSource:
    root: Path
    resolved_sha: str
    from_local: bool


def fetch_source(
    manifest: Manifest,
    *,
    resolved_sha: str | None = None,
    env: Mapping[str, str] = os.environ,
) -> FetchedSource:
    """Return the loadout source tree and resolved commit.

    When ``resolved_sha`` is None, resolve ``manifest.ref`` from the remote
    (or use ``LOADOUT_PATH`` when set). When an explicit SHA is passed, probe
    the cache for that commit only and do not re-resolve the ref (used by
    ``update`` changelog helpers).
    """
    local_path = env.get("LOADOUT_PATH")
    if local_path:
        root = Path(local_path).expanduser()
        if not root.is_dir():
            raise ValidationError(f"LOADOUT_PATH is not a directory: {root}")
        return FetchedSource(root=root.resolve(), resolved_sha="local", from_local=True)

    cache_key_sha = resolved_sha or _resolve_sha(manifest)
    cache_root = _cache_root(env)
    # Cache probe only; clone path determines the returned commit on cache miss.
    destination = cache_root / cache_key_sha
    if destination.is_dir():
        return FetchedSource(root=destination, resolved_sha=cache_key_sha, from_local=False)
    if destination.exists():
        raise FetchError(f"Source cache path is not a directory: {destination}")

    ref = resolved_sha or manifest.ref
    return _clone_to_cache(manifest.source, ref, cache_root)


def _cache_root(env: Mapping[str, str]) -> Path:
    cache_home = env.get("XDG_CACHE_HOME")
    if cache_home:
        return Path(cache_home).expanduser() / "loadout" / "sources"
    return Path.home() / ".cache" / "loadout" / "sources"


def _resolve_sha(manifest: Manifest) -> str:
    result = _run_git(["git", "ls-remote", manifest.source, manifest.ref])
    resolved_sha: str | None = None
    for line in result.stdout.strip().splitlines():
        fields = line.split(maxsplit=1)
        if not fields:
            continue
        sha = fields[0]
        if not sha:
            continue
        if resolved_sha is None:
            resolved_sha = sha
        if len(fields) == 2 and fields[1].endswith("^{}"):
            return sha
    if resolved_sha is None:
        raise FetchError(f"Could not resolve ref {manifest.ref!r} from {manifest.source!r}")
    return resolved_sha


def _clone_to_cache(source: str, ref: str, cache_root: Path) -> FetchedSource:
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache_root) as temp_dir:
            checkout = Path(temp_dir) / "checkout"
            _run_git(["git", "init", str(checkout)])
            _run_git(["git", "-C", str(checkout), "remote", "add", "origin", source])
            _run_git(["git", "-C", str(checkout), "fetch", "--depth", "1", "origin", ref])
            result = _run_git(["git", "-C", str(checkout), "rev-parse", "FETCH_HEAD^{commit}"])
            commit_sha = result.stdout.strip()
            destination = cache_root / commit_sha
            if destination.is_dir():
                return FetchedSource(root=destination, resolved_sha=commit_sha, from_local=False)
            if destination.exists():
                raise FetchError(f"Source cache path is not a directory: {destination}")
            _run_git(["git", "-C", str(checkout), "checkout", "--detach", commit_sha])
            shutil.move(str(checkout), destination)
            return FetchedSource(root=destination, resolved_sha=commit_sha, from_local=False)
    except OSError as error:
        raise FetchError(f"Could not cache source from {source!r}: {error}") from error


def _git_timeout_seconds() -> float:
    override = os.environ.get(_GIT_TIMEOUT_ENV)
    if override is not None and override.strip():
        return float(override)
    return _DEFAULT_GIT_TIMEOUT_SECONDS


def _run_git(command: list[str]) -> subprocess.CompletedProcess[str]:
    timeout = _git_timeout_seconds()
    try:
        return subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        process = getattr(error, "process", None)
        if process is not None:
            process.kill()
        raise FetchError(
            f"Git command timed out after {timeout}s: {' '.join(command)}"
        ) from error
    except (OSError, subprocess.CalledProcessError) as error:
        stderr = getattr(error, "stderr", None)
        detail = stderr.strip() if isinstance(stderr, str) and stderr.strip() else str(error)
        raise FetchError(f"Git command failed: {detail}") from error
