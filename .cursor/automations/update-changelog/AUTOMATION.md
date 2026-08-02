---
name: Update CHANGELOG on version bump
enabled: true
repository: sazlin/loadout
triggers:
  - type: push_to_branch
    branch: main
  - type: pull_request_pushed
tools:
  - open_pull_request
---

# Update CHANGELOG on version bump

Create this Cursor Automation at [cursor.com/automations/new](https://cursor.com/automations/new) (or via `/automate`).

## UI settings

| Field | Value |
| --- | --- |
| Name | Update CHANGELOG on version bump |
| Repository | `sazlin/loadout` |
| Triggers | **Push to branch** → `main`; optionally **Pull request pushed** |
| Tools | Pull request creation enabled |
| Status | Active |

Repo-backed GitHub Actions also keep `CHANGELOG.md` current (`changelog-on-version.yml`). Prefer this Cursor Automation when you want a richer, agent-written summary; the Action provides a deterministic fallback.

## Prompt

Copy everything below into the automation prompt:

---

You update `CHANGELOG.md` when the Loadout package version changes.

### When to act

1. Inspect this trigger's commits (or the push/PR diff).
2. Detect whether the Loadout version changed in either:
   - `pyproject.toml` → `[project].version`
   - `src/loadout/__init__.py` → `__version__`
3. If the version did **not** change, do nothing and exit. Do not open a PR.
4. If `CHANGELOG.md` already has a section heading for the new version (for example `## 0.2.0`), do nothing and exit.

### What to do when the version changed

1. Determine the new version string and the previous version (from the prior commit, previous CHANGELOG heading, or git history of the version fields).
2. Gather a summary of user-facing changes since the last version change:
   - Prefer `git log` / merged PR titles between the commit that last changed the version and `HEAD`.
   - You may also run `python tools/update_changelog.py --dry-run` for a commit-derived draft.
   - Focus on user-visible CLI, sync behavior, loadouts, rules, and skills changes.
   - Ignore pure chore/docs/test-only noise unless it affects users.
3. Read the existing `CHANGELOG.md` and match its style:
   - Top-level `# CHANGELOG`
   - Version sections as `## X.Y.Z` (newest first)
   - Bullet list of concise user-facing notes
4. Insert a new section for the new version at the top (below the `# CHANGELOG` heading).
5. Do not invent features. Only record real changes evidenced by commits, PRs, or the diff.
6. Keep version fields in sync if one of `pyproject.toml` / `__version__` was updated but not the other — only when clearly part of the same bump; otherwise leave them alone and note the mismatch in the PR body.
7. Open a pull request titled `docs: changelog for vX.Y.Z` that updates `CHANGELOG.md` (and only other files if needed for version sync). The PR body should briefly list the sources you used (commit range / key PRs).

### Quality bar

- Skip if there is nothing meaningful to say beyond "version bump".
- Keep bullets short and concrete.
- Never rewrite older changelog sections.

---
