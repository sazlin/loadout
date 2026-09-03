# Remote Ref Synchronization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every remote `loadout sync` resolve the manifest ref again, update the lockfile to that commit, and fail without project changes when the remote is unavailable.

**Architecture:** Stop using the old lockfile SHA as the default fetch input. `fetch_source` will resolve the manifest ref unless a caller explicitly supplies the SHA of an already completed sync. Synchronization keeps the previous lock only for drift detection and safe pruning. Update restores the original manifest when synchronization raises a Loadout error.

**Tech Stack:** Python 3.12, Click, pytest, Git CLI, uv, just

## Global constraints

- Keep the lockfile schema and version unchanged.
- Preserve `LOADOUT_PATH` behavior and `resolved_sha: local`.
- Resolve the remote before planning or writing project files.
- A failed remote resolution must leave the manifest, lockfile, and managed files unchanged.
- `sync --check` must resolve the remote but write nothing.
- Do not delete files absent from the previous lockfile.
- Add no dependency or configuration option.

---

### Task 1: Fresh remote resolution and lock updates

**Files:**
- Modify: `src/loadout/fetch.py:1-111`
- Modify: `src/loadout/sync.py:132-153`
- Modify: `src/loadout/cli.py:104-121`
- Modify: `src/loadout/update.py:27-47`
- Modify: `tests/test_fetch.py:42-115`
- Modify: `tests/test_sync.py:38-77,511-595`

**Interfaces:**
- Produces: `fetch_source(manifest: Manifest, *, resolved_sha: str | None = None, env: Mapping[str, str] = os.environ) -> FetchedSource`
- `resolved_sha=None` means resolve `manifest.ref` from the remote now.
- An explicit `resolved_sha` means retrieve that exact already-selected commit, primarily for update changelog reporting.
- `LOADOUT_PATH` continues to take precedence and returns `resolved_sha="local"`.

- [ ] **Step 1: Replace the locked-source fetch tests with fresh-resolution tests**

Replace `test_fetch_reuses_cached_locked_source` and `test_fetch_uses_matching_lock_without_resolving_ref` with tests equivalent to:

```python
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
```

Update the remaining fetch tests to call `fetch_source(manifest)` without a lock argument.

- [ ] **Step 2: Add remote-version helpers and failing sync behavior tests**

In `tests/test_sync.py`, add `import loadout.sync as sync_module`, import `FetchError`, `FetchedSource`, and `Manifest`, then add:

```python
def fetched_version(tmp_path: Path, name: str, sha: str) -> FetchedSource:
    source = tmp_path / name
    shutil.copytree(FIXTURE, source)
    return FetchedSource(root=source, resolved_sha=sha, from_local=False)


def use_remote_versions(monkeypatch: pytest.MonkeyPatch, *versions: FetchedSource) -> None:
    remaining = iter(versions)

    def fetch_current(manifest: Manifest) -> FetchedSource:
        assert manifest.ref == "main"
        return next(remaining)

    monkeypatch.setattr(sync_module, "fetch_source", fetch_current)


def test_sync_refreshes_remote_ref_and_records_new_sha(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = fetched_version(tmp_path, "first", "a" * 40)
    second = fetched_version(tmp_path, "second", "b" * 40)
    (second.root / "rules/core/a.mdc").write_text("---\ndescription: Updated rule\n---\n\nUpdated.\n")
    write_manifest(project, manifest_body().replace("ref: v1.0.0", "ref: main"))
    use_remote_versions(monkeypatch, first, second)

    sync(project)
    sync(project)

    assert "Updated." in (project / RULE_A).read_text()
    assert read_lock(project)["resolved_sha"] == "b" * 40


def test_sync_refresh_prunes_files_missing_from_new_remote(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = fetched_version(tmp_path, "first", "c" * 40)
    second = fetched_version(tmp_path, "second", "d" * 40)
    (second.root / "loadouts/base.yaml").write_text(
        "name: base\ndescription: Base rules and skills\n"
        "skills:\n  - src: skills/demo\n"
        "hooks:\n  - src: hooks/demo\n"
        "mcps:\n  - src: mcps/demo-docs\n"
    )
    write_manifest(project, manifest_body().replace("ref: v1.0.0", "ref: main"))
    use_remote_versions(monkeypatch, first, second)

    sync(project)
    sync(project)

    assert not (project / RULE_A).exists()
    assert read_lock(project)["resolved_sha"] == "d" * 40


def test_check_reports_advanced_remote_sha_without_writing(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = fetched_version(tmp_path, "first", "e" * 40)
    second = fetched_version(tmp_path, "second", "f" * 40)
    write_manifest(project, manifest_body().replace("ref: v1.0.0", "ref: main"))
    use_remote_versions(monkeypatch, first, second)
    sync(project)
    before = snapshot(project)

    with pytest.raises(DriftError, match="resolved_sha"):
        sync(project, check=True)

    assert snapshot(project) == before


def test_remote_resolution_failure_leaves_project_unchanged(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = fetched_version(tmp_path, "first", "1" * 40)
    write_manifest(project, manifest_body().replace("ref: v1.0.0", "ref: main"))
    use_remote_versions(monkeypatch, first)
    sync(project)
    before = snapshot(project)

    def fail_fetch(manifest: Manifest) -> FetchedSource:
        assert manifest.ref == "main"
        raise FetchError("remote unavailable")

    monkeypatch.setattr(sync_module, "fetch_source", fail_fetch)

    with pytest.raises(FetchError, match="remote unavailable"):
        sync(project)

    assert snapshot(project) == before
```

- [ ] **Step 3: Run the new tests and verify they fail**

Run:

```bash
uv run pytest tests/test_fetch.py tests/test_sync.py -q
```

Expected: the fetch API and advanced-ref assertions fail because the current implementation reuses the lock SHA.

- [ ] **Step 4: Make fresh resolution the default fetch behavior**

In `src/loadout/fetch.py`:

```python
def fetch_source(
    manifest: Manifest,
    *,
    resolved_sha: str | None = None,
    env: Mapping[str, str] = os.environ,
) -> FetchedSource:
    local_path = env.get("LOADOUT_PATH")
    if local_path:
        root = Path(local_path).expanduser()
        if not root.is_dir():
            raise ValidationError(f"LOADOUT_PATH is not a directory: {root}")
        return FetchedSource(root=root.resolve(), resolved_sha="local", from_local=True)

    commit_sha = resolved_sha or _resolve_sha(manifest)
    cache_root = _cache_root(env)
    destination = cache_root / commit_sha
    if destination.is_dir():
        return FetchedSource(root=destination, resolved_sha=commit_sha, from_local=False)
    if destination.exists():
        raise FetchError(f"Source cache path is not a directory: {destination}")

    _clone_to_cache(manifest.source, commit_sha, cache_root, destination)
    return FetchedSource(root=destination, resolved_sha=commit_sha, from_local=False)
```

Remove the `Lockfile` import and `_locked_sha`. Migrate every caller:

```python
# sync.py and cli.py resolve/list path
fetched = fetch_source(manifest)

# update.py after a successful sync
fetched = fetch_source(updated_manifest, resolved_sha=lock.resolved_sha)
```

Remove now-unused lock loading from `cli._print_resolved`. Keep lock loading in `sync` for drift and pruning and in `update` for the completed sync SHA.

- [ ] **Step 5: Run focused tests and verify they pass**

Run:

```bash
uv run pytest tests/test_fetch.py tests/test_sync.py tests/test_cli.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit the fresh-resolution change**

```bash
git add src/loadout/fetch.py src/loadout/sync.py src/loadout/cli.py src/loadout/update.py tests/test_fetch.py tests/test_sync.py
git commit -m "fix: refresh remote refs during sync"
```

---

### Task 2: Transactional update failure

**Files:**
- Modify: `src/loadout/update.py:27-47,71-75`
- Modify: `tests/test_cli.py:257-302`

**Interfaces:**
- Consumes: fresh `fetch_source` semantics from Task 1.
- Produces: `update(project_root: Path, *, to_ref: str | None = None) -> UpdateResult` that restores the original manifest text when `run_sync` raises `LoadoutError`.

- [ ] **Step 1: Add a failing update rollback test**

Import `FetchError` in `tests/test_cli.py`. Add:

```python
def test_update_restores_manifest_when_remote_sync_fails(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    with runner.isolated_filesystem():
        original = "source: https://example.com/loadout\nref: v1.0.0\nloadouts: [python]\n"
        Path(".loadout.yaml").write_text(original)

        def fail_sync(project_root: Path) -> None:
            raise FetchError("remote unavailable")

        monkeypatch.setattr("loadout.update.run_sync", fail_sync)

        result = runner.invoke(main, ["update", "--to", "main"])

        assert result.exit_code == 3
        assert Path(".loadout.yaml").read_text() == original
        assert not Path(".loadout.lock").exists()
```

- [ ] **Step 2: Run the rollback test and verify it fails**

Run:

```bash
uv run pytest tests/test_cli.py::test_update_restores_manifest_when_remote_sync_fails -q
```

Expected: FAIL because the manifest remains changed to `ref: main`.

- [ ] **Step 3: Restore the manifest on Loadout failures**

Import `LoadoutError` and preserve the original text before rewriting:

```python
original_manifest = manifest_path.read_text()
_rewrite_ref(manifest_path, new_ref)
try:
    run_sync(project_root)
except LoadoutError:
    manifest_path.write_text(original_manifest)
    raise
```

Catch only `LoadoutError`. Do not hide or translate the original error.

- [ ] **Step 4: Run update and CLI tests**

Run:

```bash
uv run pytest tests/test_cli.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit transactional update behavior**

```bash
git add src/loadout/update.py tests/test_cli.py
git commit -m "fix: restore manifest after failed update"
```

---

### Task 3: User-facing semantics and full verification

**Files:**
- Modify: `src/loadout/cli.py:35-55`
- Modify: `README.md:24-135,219-227`
- Modify: `CHANGELOG.md:3-7`

**Interfaces:**
- Documents that remote sync resolves the configured ref on every run.
- Documents that the lock records the exact commit used by the last successful sync.
- Documents that `sync --check` compares against the current remote ref.

- [ ] **Step 1: Update CLI help text**

Use descriptions equivalent to:

```python
def sync(check: bool) -> None:
    """Apply the current remote loadout ref, or check it for drift."""


def update(to_ref: str | None) -> None:
    """Select a ref, re-sync it from the remote, and print its CHANGELOG entries."""
```

Keep option names and defaults unchanged.

- [ ] **Step 2: Update README behavior documentation**

State these facts in the Quick start, Pull loadout changes, Check for drift, and manifest field descriptions:

- `sync` resolves the configured remote ref every time.
- `ref: main` follows the latest remote `main` head.
- A release tag gives a stable upgrade cadence.
- `.loadout.lock` stores the exact resolved commit and managed-file inventory.
- `sync --check` contacts the remote and reports drift when the ref advanced.
- Removing a loadout from `.loadout.yaml` and syncing prunes only its previously locked managed files.

Do not add a separate guide or duplicate the command examples.

- [ ] **Step 3: Add an Unreleased changelog entry**

Add one bullet under `## Unreleased`:

```markdown
- Resolve the configured remote ref on every `loadout sync`, update the lockfile to the fetched commit, and prune managed files no longer selected.
```

- [ ] **Step 4: Run focused verification**

```bash
uv run pytest tests/test_fetch.py tests/test_sync.py tests/test_cli.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run repository verification**

```bash
just lint
just test
just typecheck
```

Expected: every command exits zero, with no lint, test, or type errors.

- [ ] **Step 6: Smoke-test the CLI against a Git source**

From a temporary target project, invoke the current checkout without `LOADOUT_PATH`:

```bash
TARGET="$(mktemp -d)"
cd "$TARGET"
uv run --project /Users/seanazlin/Repos/loadout loadout init \
  --loadouts base \
  --source /Users/seanazlin/Repos/loadout \
  --ref fix/sync-refresh-refs
uv run --project /Users/seanazlin/Repos/loadout loadout sync
uv run --project /Users/seanazlin/Repos/loadout loadout sync --check
```

Expected: sync succeeds, `.loadout.lock` records the branch commit SHA rather than `local`, and check reports no drift.

- [ ] **Step 7: Commit documentation**

```bash
git add README.md CHANGELOG.md src/loadout/cli.py
git commit -m "docs: explain remote ref synchronization"
```

- [ ] **Step 8: Review final diff and commit messages**

Inspect the branch diff against `main`, confirm only planned files changed, and verify no commit message contains a Cursor co-author.
