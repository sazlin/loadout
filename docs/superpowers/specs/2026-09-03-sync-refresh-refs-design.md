# Remote ref synchronization design

## Goal

Make `loadout sync` synchronize a project with the current remote value of the `ref` in `.loadout.yaml`. With `ref: main`, every successful sync must use the commit currently at the head of the remote `main` branch.

A remote resolution failure must stop the command before it changes the project.

## Decisions

| Topic | Choice |
| --- | --- |
| `sync` remote behavior | Resolve the manifest ref on every remote sync |
| Network failure | Fail before changing managed files or the lockfile |
| Lockfile schema | Keep `source`, `ref`, `resolved_sha`, file inventory, and managed blocks |
| Cached sources | Reuse a cached checkout by resolved commit hash |
| `sync --check` | Resolve the current remote ref and report drift without writing |
| `update --to main` | Rewrite the requested ref and run a fresh sync, even when it was already `main` |
| `LOADOUT_PATH` | Preserve local-development behavior and record `resolved_sha: local` |

## Current problem

`fetch_source` currently prefers the lockfile's `resolved_sha` whenever the lockfile and manifest have matching `source` and `ref` values. A project can therefore have `ref: main` while repeated `loadout sync` and `loadout update --to main` calls continue using an old commit.

The lockfile is acting as both an installation record and a source-selection input. Those responsibilities conflict for mutable refs.

## Lockfile responsibilities

The lockfile remains an exact record of the last successful synchronization. It keeps:

- `source`, to record where the loadout came from.
- `ref`, to record the requested branch or tag.
- `resolved_sha`, to record the exact commit installed.
- `files` and `managed_blocks`, to identify managed content, detect drift, and remove stale content safely.
- `tool_version` and `synced_at`, to preserve audit information.

The lockfile's `resolved_sha` must not choose the source commit for a new remote sync. The manifest supplies the requested source and ref. Remote resolution supplies the commit.

No lockfile schema or version change is required.

## Synchronization flow

For a normal remote-backed sync:

1. Read `.loadout.yaml` and the existing `.loadout.lock`.
2. Resolve the manifest's `source` and `ref` against the remote.
3. If resolution fails, return an error before planning or applying changes.
4. Use the checkout cached under the resolved commit hash, or fetch that exact commit into the cache.
5. Resolve and validate the selected loadouts from that checkout.
6. Build the desired file and managed-block plan.
7. Use the previous lockfile inventory to remove managed files that are absent from the new plan.
8. Add or update desired managed content.
9. Write a lockfile containing the newly resolved commit.
10. Run configured CLI tools after file synchronization, preserving current behavior.

Resolving the ref before fetching the exact commit gives one consistent source snapshot even if the branch advances during the command.

## Command behavior

### `loadout sync`

Every remote sync resolves the manifest ref again. If `.loadout.yaml` contains `ref: main`, the command uses the current remote `main` head rather than the commit stored in the existing lockfile.

A successful sync updates `resolved_sha` when the remote ref advanced. It also removes stale managed content by comparing the new plan with the previous lockfile inventory.

### `loadout sync --check`

Check mode performs the same remote ref resolution and planning but writes nothing and does not run CLI tools.

If the remote ref resolves to a commit different from the lockfile, check mode reports `resolved_sha` drift and exits nonzero. Network failure is an error, not permission to check against stale cached content.

### `loadout update --to REF`

Update writes the requested `ref`, then invokes the fresh synchronization behavior. `loadout update --to main` therefore resolves remote `main` even when the manifest already contains `ref: main`.

If the target ref cannot be resolved, update must leave `.loadout.yaml`, `.loadout.lock`, and managed content unchanged. Implementation may preflight target resolution or restore the manifest on failure, but partial manifest updates are not acceptable.

### `loadout update`

The no-argument command continues selecting the latest release tag and then synchronizes it. The synchronization still resolves that selected tag against the remote.

### Local development

When `LOADOUT_PATH` is set, Loadout continues reading directly from that directory without contacting the configured remote. The lockfile continues recording `resolved_sha: local`.

## Failure handling

Remote resolution and source checkout must complete before project writes begin. These failures leave the manifest, lockfile, and managed files unchanged:

- The source is unreachable.
- The requested ref does not exist.
- Git returns no commit for the ref.
- The resolved commit cannot be fetched or checked out.

Existing validation errors also remain pre-apply failures. CLI tool failures retain their current post-sync, non-transactional behavior and are outside this change.

## Compatibility

Existing manifests and lockfiles remain valid. The next successful remote sync may advance a branch or other moved ref and update managed files immediately. This is the intended behavior change.

Consumers that require a fixed source should use a stable release tag. The lockfile still records the exact commit installed, but ordinary remote sync now verifies the manifest ref rather than treating the lock as a permanent source pin.

## Verification

Add focused coverage for these observable contracts:

1. A matching manifest and lock with `ref: main` still resolves the remote.
2. When remote `main` advances, `sync` applies the new content and writes the new `resolved_sha`.
3. An advancing ref prunes files present only in the previous lock and source revision.
4. `sync --check` reports drift when the remote ref advances and writes nothing.
5. Remote resolution failure leaves managed files and the lockfile unchanged.
6. `update --to main` refreshes an already-`main` manifest.
7. Update failure leaves the manifest, lockfile, and managed files unchanged.
8. `LOADOUT_PATH` retains local behavior without remote resolution.
9. A cache hit for the newly resolved commit avoids cloning it again.

Run the focused fetch, sync, update, and CLI tests, followed by `just lint`, `just test`, and `just typecheck`.

## Out of scope

- Removing user-owned files that do not appear in the previous lockfile.
- Changing loadout selection from the command line.
- Adding offline fallback to the previously locked commit.
- Changing CLI tool failure behavior.
- Changing cache layout or eviction.
