from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from loadout import fetch
from loadout.errors import FetchError, ValidationError
from loadout.fetch import fetch_source
from loadout.models import Manifest


def make_manifest() -> Manifest:
    return Manifest(
        source="https://example.com/loadouts.git",
        ref="main",
        loadouts=["base"],
    )


def run_git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def test_fetch_uses_loadout_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setenv("LOADOUT_PATH", str(source))

    fetched = fetch_source(make_manifest())

    assert fetched.from_local is True
    assert fetched.resolved_sha == "local"
    assert fetched.root == source.resolve()


def test_fetch_rejects_missing_loadout_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing_source = tmp_path / "missing"
    monkeypatch.setenv("LOADOUT_PATH", str(missing_source))

    with pytest.raises(ValidationError, match="LOADOUT_PATH"):
        fetch_source(make_manifest())


def test_fetch_resolves_ref_before_reusing_cached_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resolved_sha = "a" * 40
    cache_source = tmp_path / "loadout" / "sources" / resolved_sha
    cache_source.mkdir(parents=True)
    monkeypatch.delenv("LOADOUT_PATH", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(fetch, "_resolve_sha", lambda manifest: resolved_sha)

    def fail_if_cloning(*args: object) -> None:
        pytest.fail("cached resolved commit should not be cloned")

    monkeypatch.setattr(fetch, "_clone_to_cache", fail_if_cloning)

    fetched = fetch_source(make_manifest())

    assert fetched.resolved_sha == resolved_sha
    assert fetched.root == cache_source


def test_fetch_accepts_an_explicit_resolved_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resolved_sha = "b" * 40
    cache_source = tmp_path / "loadout" / "sources" / resolved_sha
    cache_source.mkdir(parents=True)
    monkeypatch.delenv("LOADOUT_PATH", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    def fail_if_resolving(manifest: Manifest) -> str:
        pytest.fail(f"unexpected ref resolution for {manifest.ref}")

    monkeypatch.setattr(fetch, "_resolve_sha", fail_if_resolving)

    fetched = fetch_source(make_manifest(), resolved_sha=resolved_sha)

    assert fetched.resolved_sha == resolved_sha
    assert fetched.root == cache_source


def test_fetch_uses_commit_fetched_from_moving_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    run_git(repository, "init", "-b", "main")
    run_git(repository, "config", "user.name", "Test User")
    run_git(repository, "config", "user.email", "test@example.com")
    content = repository / "content.txt"
    content.write_text("old\n")
    run_git(repository, "add", "content.txt")
    run_git(repository, "commit", "-m", "old")
    old_sha = run_git(repository, "rev-parse", "HEAD")
    content.write_text("new\n")
    run_git(repository, "commit", "-am", "new")
    new_sha = run_git(repository, "rev-parse", "HEAD")
    manifest = Manifest(source=str(repository), ref="main", loadouts=["base"])
    monkeypatch.delenv("LOADOUT_PATH", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(fetch, "_resolve_sha", lambda manifest: old_sha)

    fetched = fetch_source(manifest)

    assert fetched.resolved_sha == new_sha
    assert (fetched.root / "content.txt").read_text() == "new\n"


def test_resolve_sha_prefers_peeled_annotated_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tag_object_sha = "e" * 40
    commit_sha = "f" * 40
    output = f"{tag_object_sha}\trefs/tags/v1.0.0\n{commit_sha}\trefs/tags/v1.0.0^{{}}\n"
    monkeypatch.setattr(
        fetch,
        "_run_git",
        lambda command: subprocess.CompletedProcess(command, 0, stdout=output),
    )
    manifest = Manifest(
        source="https://example.com/loadouts.git",
        ref="refs/tags/v1.0.0",
        loadouts=["base"],
    )

    assert fetch._resolve_sha(manifest) == commit_sha


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
        fetch_source(make_manifest())


def test_fetch_git_timeout_raises_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    monkeypatch.setenv("LOADOUT_GIT_TIMEOUT_SECONDS", "0.2")

    start = time.monotonic()
    with pytest.raises(FetchError, match="timed out after 0.2s"):
        fetch._run_git(["sleep", "30"])
    assert time.monotonic() - start < 2.0
