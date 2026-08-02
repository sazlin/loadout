from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from loadout.errors import FetchError, ValidationError
from loadout.fetch import fetch_source
from loadout.models import Lockfile, Manifest


def make_manifest() -> Manifest:
    return Manifest(
        source="https://example.com/loadouts.git",
        ref="main",
        loadouts=["base"],
    )


def test_fetch_uses_loadout_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setenv("LOADOUT_PATH", str(source))

    fetched = fetch_source(make_manifest(), None)

    assert fetched.from_local is True
    assert fetched.resolved_sha == "local"
    assert fetched.root == source.resolve()


def test_fetch_rejects_missing_loadout_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_source = tmp_path / "missing"
    monkeypatch.setenv("LOADOUT_PATH", str(missing_source))

    with pytest.raises(ValidationError, match="LOADOUT_PATH"):
        fetch_source(make_manifest(), None)


def test_fetch_reuses_cached_locked_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved_sha = "a" * 40
    cache_source = tmp_path / "loadout" / "sources" / resolved_sha
    cache_source.mkdir(parents=True)
    monkeypatch.delenv("LOADOUT_PATH", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    lock = Lockfile(
        lockfile_version=1,
        source="https://example.com/loadouts.git",
        ref="main",
        resolved_sha=resolved_sha,
        synced_at="2026-08-01T00:00:00Z",
        tool_version="0.1.0",
        files=[],
        managed_blocks=[],
    )

    fetched = fetch_source(make_manifest(), lock)

    assert fetched.from_local is False
    assert fetched.resolved_sha == resolved_sha
    assert fetched.root == cache_source


def test_fetch_wraps_git_resolution_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOADOUT_PATH", raising=False)

    def fail_git(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(
            returncode=128,
            cmd=["git", "ls-remote"],
            stderr="repository not found",
        )

    monkeypatch.setattr("loadout.fetch.subprocess.run", fail_git)

    with pytest.raises(FetchError, match="repository not found"):
        fetch_source(make_manifest(), None)
