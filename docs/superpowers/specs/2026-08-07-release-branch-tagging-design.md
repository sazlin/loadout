# Release branch tagging design

## Goal

Stop tagging releases from the default branch tip. Every release is prepared on a dedicated `release/vX.Y.Z` branch off `main`/`master`, merged via PR, and annotated-tagged automatically by CI on the merge commit.

## Decisions

| Topic | Choice |
| --- | --- |
| Branch name | `release/vX.Y.Z` (must include the `v` prefix) |
| Local `just release` | On existing `release/vX.Y.Z`: validate, push, open PR via `gh`; never tag or create the branch |
| On merge | Annotated git tag `vX.Y.Z` only (no GitHub Release object) |
| Workflow approach | PR-closed+merged trigger with idempotent skip if tag exists, plus CHANGELOG/version checks |

## End-to-end flow

1. Start from an up-to-date `main` or `master`.
2. Create dedicated branch `release/vX.Y.Z` from that default branch.
3. On that branch only: move CHANGELOG bullets under `## X.Y.Z`, bump `pyproject.toml` / `__version__` / lockfile, commit.
4. Run `just release X.Y.Z` (must already be on `release/vX.Y.Z`): validates CHANGELOG + version files, runs lint/test, pushes the branch, opens a PR into the default branch via `gh`.
5. After review and green CI, merge the PR.
6. Workflow `tag-release` runs on the merged PR, extracts `X.Y.Z` from `head_ref`, validates versions, and creates annotated tag `vX.Y.Z` on `pull_request.merge_commit_sha`.

## Skill changes (`skills/release-checklist`)

Update the skill so agents always:

1. Confirm intended semver, release scope, and that work starts from `main`/`master`.
2. Create dedicated branch `release/vX.Y.Z` from the default branch tip — never land release commits directly on the default branch.
3. Commit version bumps and CHANGELOG updates on that branch only.
4. Review the full diff and user-facing CHANGELOG for that version.
5. Run required lint, test, build, and packaging checks from a clean state (or via `just release`).
6. Verify version consistency across branch name (`release/vX.Y.Z`), `CHANGELOG.md` (`## X.Y.Z`), `pyproject.toml`, and `src/loadout/__init__.py`.
7. Publish with `just release X.Y.Z` (push + PR) and merge; **do not** create or push git tags locally — CI owns tagging.
8. After merge, confirm the annotated tag exists; record rollback as “consumers pin previous tag.”

## `just release` changes

Replace local tag/push with a publish helper that assumes the release branch and commits already exist:

1. Resolve default branch (`main` preferred, else `master`) for the PR base.
2. Fail unless the current branch is exactly `release/v{{version}}`.
3. Fail unless `CHANGELOG.md` contains `## {{version}}`.
4. Fail unless `pyproject.toml` and `src/loadout/__init__.py` versions equal `{{version}}`.
5. Run `just lint && just test`.
6. `git push -u origin HEAD` (fail if the branch cannot be pushed).
7. `gh pr create` targeting the default branch (title/body include the version); if a PR already exists for the branch, print its URL instead of failing.
8. Print next steps (merge PR → CI tags).

Do not create the release branch, commit version bumps, run `git tag`, or push tags. Branch creation and version commits remain skill/agent (or human) steps before invoking the recipe.

Update README’s release one-liner to match.

## Workflow (`.github/workflows/tag-release.yml`)

Keep `.github/workflows/ci.yml` unchanged.

```yaml
on:
  pull_request:
    types: [closed]
    branches: [main, master]
```

Job guard:

- `github.event.pull_request.merged == true`
- `github.head_ref` matches `^release/v[0-9]+\.[0-9]+\.[0-9]+$`

Permissions: `contents: write`.

Steps:

1. Checkout `github.event.pull_request.merge_commit_sha`.
2. Parse version from `head_ref` (`release/v` + semver); fail on mismatch.
3. Assert `CHANGELOG.md` contains `## $VERSION`.
4. Assert package version in `pyproject.toml` and `src/loadout/__init__.py` equals `$VERSION`.
5. If remote tag `v$VERSION` already exists, exit 0 with a skip message.
6. Otherwise create annotated tag `v$VERSION` on the merge commit and push it to `origin`.

## Edge cases

| Case | Behavior |
| --- | --- |
| Non-`release/v*` PR merged | Job skipped |
| Malformed branch (`release/v1.2`, `release/1.2.3`) | Job fails |
| Branch/CHANGELOG/pyproject version mismatch | Fail before tagging |
| Tag already exists | Skip, success |
| Direct push to default branch (no PR) | No tag (by design) |

## Out of scope

- Creating GitHub Release objects / release notes UI
- Consumer fan-out / `repository_dispatch`
- Changes to the existing CI matrix

## Rollback

Consumers pin the previous tag (e.g. `@v0.2.0`). Deleting a remote tag is a deliberate yank, not the default rollback path.

## Verification (for implementing this change)

- Skill and README describe the branch/PR/CI-tag flow.
- `just release` no longer tags or creates the branch; it validates an existing `release/v*` branch, pushes, and opens a PR.
- Workflow file present with guards, version checks, and idempotent tag skip.
- Manual smoke: open a dry-run PR from a throwaway `release/v*` branch only if needed; parse/guard logic can be reviewed statically in-repo.
