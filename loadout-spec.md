# Spec: `loadout`

Centralized, versioned Cursor rules and skills, composed per project and vendored into each project repo.

Status: ready to implement
Audience: implementing engineer or coding agent

---

## 1. Problem

We generate Python monorepo projects from a cookiecutter metafactory template (UV workspaces, Terraform on AWS, Playwright). Every generated project needs Cursor rules and skills. Most are shared across all projects. Some apply only to projects with a given feature, and some must be explicitly absent from projects that do not have that feature.

We need the rules and skills to live in their own git repo with their own release cycle, while each project holds a concrete, reviewable copy of exactly the set it uses.

## 2. Approach

One source-of-truth repo (`loadout`) publishes rules, skills, and named loadouts. Each project repo commits a small manifest that pins a repo version and selects one or more named loadouts. A `sync` command copies the resolved file set into the project's `.cursor/` directories. The generated output is committed.

Vendoring is deliberate. Cursor discovers rules and skills as real files on disk, so a copy has to exist in the project anyway. Committing it means teammates, CI, and cloud agents get the correct set with no setup, and any change to agent instructions arrives as a reviewable diff.

Rejected alternatives:

- **Git submodule of the loadout repo.** All-or-nothing. Cannot select a subset, and per-project exclusions have nowhere to live.
- **Symlinks into a shared checkout.** Breaks on Windows, cloud agents, and some CI checkout modes. Not portable in git.
- **Cursor Marketplace plugin.** Installs are user-level, not committed per repo, so per-project inclusion and exclusion cannot be enforced or reviewed.

## 3. Definitions

| Term | Meaning |
| --- | --- |
| Loadout repo | The `loadout` repo. The single source of truth for all rules, skills, and loadout definitions |
| Rule | A `.mdc` file with YAML frontmatter, loaded by Cursor from `.cursor/rules/` |
| Skill | A directory whose root contains `SKILL.md`, optionally with bundled `scripts/`, `references/`, `assets/`, `agents/`, and `evals/` subtrees. Loaded from `.claude/skills/`, which both Cursor and Claude Code read. See sections 5.2 and 5.7 |
| Hook | A directory under `hooks/` with `hook.yaml` plus scripts/assets. Synced once to `.cursor/hooks/<name>/`. Sync also generates `.cursor/hooks.json` (Cursor-native) and `.claude/settings.json` hooks (Claude Code) that both point at that single script copy. See section 5.9 |
| Loadout | A named, composable selection of rules, skills, and hooks, defined in the loadout repo and selected by a project. The unit a project actually chooses |
| Manifest | `.loadout.yaml`, committed in each project |
| Lockfile | `.loadout.lock`, committed in each project |
| Sync | Resolving the manifest and writing the file set into the project |

---

## 4. Repository layout

### 4.1 `loadout`

```
loadout/
  justfile
  pyproject.toml              # packages the `loadout` CLI
  src/loadout/
    __init__.py
    cli.py
    resolve.py                # manifest + loadouts -> file list
    sync.py                   # write, check, prune
    lock.py
  rules/
    core/
      commit-style.mdc
      repo-conventions.mdc
    python/
      python-code-style.mdc
      uv-workspace.mdc
      pytest.mdc
    typescript/
      typescript-code-style.mdc
    terraform/
      aws-conventions.mdc
    playwright/
      e2e-conventions.mdc
  skills/
    db-migrations/SKILL.md
    release-checklist/SKILL.md
    terraform-plan-review/SKILL.md
  hooks/
    deny-dangerous/
      hook.yaml
      deny-dangerous.sh
      dangerous-patterns.txt
      test-guard.sh
  loadouts/
    base.yaml
    python.yaml
    python-monorepo.yaml
    typescript.yaml
    aws-terraform.yaml
    playwright-e2e.yaml
  tests/
  CHANGELOG.md
```

The CLI ships from the loadout repo on purpose. A project invokes it at its pinned ref, so tool and content are always version-matched.

### 4.2 Generated project (relevant parts)

```
my-project/
  .loadout.yaml                 # hand-editable, committed
  .loadout.lock                 # generated, committed
  justfile                      # includes loadout recipes
  AGENTS.md                     # hand-owned, with ONE generated block (5.7)
  CLAUDE.md                     # hand-owned, with ONE generated block (5.8)
  .cursor/
    rules/                      # GENERATED, committed
  .claude/skills/               # GENERATED, committed. Read by Cursor AND Claude Code
  infra/.cursor/rules/          # GENERATED, scoped to infra/
  infra/.claude/skills/         # GENERATED, scoped to infra/
  tests/e2e/.cursor/rules/      # GENERATED, scoped to tests/e2e/
  packages/…
```

---

## 5. File formats

### 5.1 Rule (`.mdc`)

```markdown
---
description: Conventions for UV workspace layout and dependency management
globs: ["**/pyproject.toml", "packages/**/*.py"]
alwaysApply: false
---

# UV workspace conventions
...
```

Rules with `alwaysApply: true` consume context in every request. Keep that set small and put it in `rules/core/` only. Everything else must be glob-scoped.

### 5.2 Skill (directory)

A skill is a **directory**, not a single file. Treat it as an opaque unit: the loadout repo stores it, sync copies the whole subtree, and nothing rewrites its internals except the generated header in `SKILL.md`.

Only `SKILL.md` at the skill root is required. Complex skills, including anything produced by Claude Code's `skill-creator`, add bundled resources alongside it.

#### 5.2.1 Anatomy

```
db-migrations/
├── SKILL.md            # REQUIRED. Frontmatter + markdown instructions
├── scripts/            # Executable code for deterministic or repetitive steps
├── references/         # Docs the agent loads into context on demand
├── assets/             # Files used in the output (templates, icons, fonts, HTML)
├── agents/             # Subagent definitions (markdown), used by multi-agent skills
└── evals/              # Test harness. NOT vendored into projects, see 5.2.4
    ├── evals.json
    └── files/          # Input fixtures referenced by evals
```

The three bundled-resource directories that carry defined meaning are `scripts/`, `references/`, and `assets/`. `agents/` appears in skills that fan work out to subagents. Any other subdirectory is copied verbatim without special handling.

This layout exists to serve **progressive disclosure**, a three-level loading model:

| Level | Content | When loaded |
| --- | --- | --- |
| 1 | `name` + `description` frontmatter | Always in context, roughly 100 words |
| 2 | `SKILL.md` body | Whenever the skill triggers, target under 500 lines |
| 3 | Bundled resources | On demand. Scripts can execute without being read into context |

Level 1 is the entire triggering mechanism, so every "when to use this" statement belongs in `description` and nowhere else. Level 2 has a real budget: Cursor concatenates loaded skills into the system prompt, so an oversized `SKILL.md` costs context on every trigger. If a skill approaches 500 lines, push detail into `references/` and leave a pointer saying when to read it. Reference files over roughly 300 lines should open with a table of contents.

#### 5.2.2 `SKILL.md` frontmatter

```markdown
---
name: db-migrations
description: Create, review, and apply Alembic migrations in this repo. Use whenever the user mentions migrations, schema changes, Alembic, or altering database tables, even if they do not say "migration" explicitly.
allowed-tools: [Bash, Read, Edit]
compatibility: Requires `uv` and a running local Postgres
license: MIT
metadata:
  owner: platform-team
---
```

Contract enforced by lint:

- Allowed keys, and no others: `name`, `description`, `license`, `allowed-tools`, `metadata`, `compatibility`. An unexpected key is a fatal error.
- `name` and `description` are required.
- `name` is kebab-case (`^[a-z0-9-]+$`), max 64 characters, no leading or trailing hyphen, no consecutive hyphens.
- `name` **must equal the containing directory name**. Cursor derives the skill name from the directory, so a mismatch produces a silently misnamed skill.
- `description` must contain no `<` or `>`.
- Descriptions should lean pushy about triggering conditions. Agents under-trigger skills more often than they over-trigger them, so state the surface contexts explicitly.

#### 5.2.3 Sync handling

- **Whole-subtree copy.** Sync copies every file under the skill directory, preserving relative paths and the executable bit on anything in `scripts/`.
- **Provenance injection into `SKILL.md` only.** Bundled resources are copied byte for byte. Injecting frontmatter into a Python script, a PNG, or an HTML asset would corrupt it.
- **Hash every file.** The lockfile records a `sha256` per file in the subtree, not one hash for the skill. Otherwise a hand-edit to `scripts/run.py` escapes `sync --check`.
- **`dest` basename must equal `src` basename.** A loadout may relocate `skills/db-migrations` to `packages/api/.claude/skills/db-migrations` but may not rename it, because the directory name is the skill name.
- **Skip junk on copy**: `__pycache__/`, `node_modules/`, `*.pyc`, `.DS_Store`.

#### 5.2.4 `evals/` stays in the loadout repo

`evals/` is test infrastructure for the skill author, not instruction content for the consuming project. Vendoring it would push fixture files and prompt sets into every project repo for no benefit, and `evals/files/` can be large.

Sync therefore **excludes `evals/` when it appears at the skill root**, matching how `skill-creator` packages skills. A directory literally named `evals/` nested deeper inside the skill is copied normally.

`evals/evals.json` follows the `skill-creator` schema:

```json
{
  "skill_name": "db-migrations",
  "evals": [
    {
      "id": 1,
      "prompt": "Add a nullable `archived_at` timestamp to the orders table",
      "expected_output": "A new Alembic revision with matching upgrade and downgrade",
      "files": ["evals/files/schema.sql"],
      "expectations": [
        "A file under alembic/versions/ was created",
        "The downgrade function drops the column"
      ]
    }
  ]
}
```

The loadout repo owns running these. See section 10.

#### 5.2.5 Workspaces are not part of the skill

`skill-creator` writes eval run output to `<skill-name>-workspace/` as a **sibling** of the skill directory, containing `iteration-N/eval-N/` run artifacts and `history.json`. These are scratch. Add `*-workspace/` to the loadout repo's `.gitignore`. They must never be committed to the loadout repo or reach a project.

### 5.3 Loadout (`loadouts/<name>.yaml`)

```yaml
name: aws-terraform
extends: [base]
description: Terraform on AWS conventions and plan review workflow

rules:
  - src: rules/terraform/aws-conventions.mdc
    dest: infra/.cursor/rules/aws-conventions.mdc

skills:
  - src: skills/terraform-plan-review
    dest: infra/.claude/skills/terraform-plan-review

hooks:
  - src: hooks/deny-dangerous
```

Rules:

- `extends` is a list and resolves depth-first. Cycles are a fatal error.
- `dest` is optional. Default for rules is `.cursor/rules/<basename>`, for skills `<skills_dir>/<dirname>` where `skills_dir` defaults to `.claude/skills`, for hooks `<hooks_dir>/<dirname>` where `hooks_dir` defaults to `.cursor/hooks`.
- Use non-default `dest` to scope content to a monorepo subtree. Cursor scopes skills found under a nested project directory to files inside that directory, which keeps Terraform guidance out of context while someone edits a Python package.
- A skill `dest` must end in `<skills_dir>/<dirname>`. Nesting is expressed by the prefix, as in `infra/.claude/skills/terraform-plan-review`.
- A hook `dest` must end in `<hooks_dir>/<dirname>`. Hook scripts are stored once under the Cursor-native path; harness config generation rewrites command paths to match.
- The same `src` appearing in two loadouts is fine and deduplicates. The same `dest` receiving two different `src` values is a fatal error.

### 5.4 Manifest (`.loadout.yaml`)

```yaml
source: https://github.com/<org>/loadout
ref: v1.4.0

loadouts:
  - base
  - python-monorepo
  - aws-terraform

include:
  - skills/db-migrations

exclude:
  - rules/python/pytest.mdc

skills_dir: .claude/skills   # optional, default .claude/skills
hooks_dir: .cursor/hooks     # optional, default .cursor/hooks
claude_bridge: true          # optional, default true. Manage the CLAUDE.md import block
```

Semantics:

- `ref` is a git tag or branch. Resolved to a commit SHA at sync time and recorded in the lockfile.
- `include` adds individual rules or skills by repo-relative `src` path, using default `dest`.
- `exclude` removes by repo-relative `src` path. Applied last. Beats both loadouts and `include`.
- **Every entry in `include` and `exclude` must match at least one path in the loadout repo at the pinned ref. A non-matching entry is a fatal error.** This is the most important validation in the spec. Without it, renaming a file in the loadout repo silently re-enables a rule a project deliberately dropped.

### 5.5 Lockfile (`.loadout.lock`)

Generated. Never hand-edited.

```json
{
  "lockfile_version": 1,
  "source": "https://github.com/<org>/loadout",
  "ref": "v1.4.0",
  "resolved_sha": "9f2c1ab…",
  "synced_at": "2026-08-01T17:04:22Z",
  "tool_version": "0.3.1",
  "files": [
    {
      "dest": ".cursor/rules/commit-style.mdc",
      "src": "rules/core/commit-style.mdc",
      "sha256": "e3b0c442…"
    },
    {
      "dest": ".claude/skills/db-migrations/scripts/new_revision.py",
      "src": "skills/db-migrations/scripts/new_revision.py",
      "sha256": "a1d0c6e8…",
      "mode": "755"
    }
  ],
  "managed_blocks": [
    { "file": "AGENTS.md", "block": "agent-rules", "sha256": "7c9f21b4…" },
    { "file": "CLAUDE.md", "block": "agents-import", "sha256": "b2e4f80a…" }
  ]
}
```

### 5.6 Generated file provenance

Every generated rule file and every generated `SKILL.md` gets loadout provenance merged into YAML frontmatter `metadata` (string keys to string values). Existing upstream `metadata` entries are preserved; loadout keys are overwritten on each sync:

```yaml
metadata:
  loadout.managed: "true"
  loadout.source: rules/core/commit-style.mdc
  loadout.sha: 9f2c1ab
```

Cursor rule application still uses only `description`, `globs`, and `alwaysApply`; the `metadata` map is ignored for attachment. For skills, `metadata` is the Agent Skills extension point for client-defined properties. Edit upstream in the loadout repo, then run `just loadout-update`.

---

### 5.7 Skill placement and the `AGENTS.md` index

Skills and rules reach non-Cursor agents by two different mechanisms, because the two formats have different levels of cross-tool support.

**Skills are portable.** `SKILL.md` is an open standard, so the same directory works in Cursor, Claude Code, Codex, and Gemini CLI unchanged. Sync writes them once, to a path both target tools read.

**Rules are not.** `.mdc` files with `globs` and `alwaysApply` are Cursor-specific. Rather than translating them into four dialects, sync publishes an **index** of them in `AGENTS.md` so any agent can find and read the relevant rule file on its own.

#### 5.7.1 Skill location

**One directory: `.claude/skills/`.** Both target tools read it, so there is nothing to mirror.

| Tool | Reads `.claude/skills/` | Notes |
| --- | --- | --- |
| Claude Code | Yes, natively | Its only project skills path. Searched in the launch directory and every parent up to the repo root |
| Cursor IDE | Yes, as a compatibility path | Cursor also loads `.cursor/skills/`, `.agents/skills/`, and `.codex/skills/` |

Picking Claude Code's native directory rather than the standard `.agents/skills/` is deliberate. Cursor reads four locations; Claude Code reads one. Choosing the intersection means a single copy, a single hash per file, and no chance of the two drifting apart.

`skills_dir` in the manifest overrides the destination if that calculus changes, for example if Codex or Gemini CLI joins the workflow and `.agents/skills/` becomes the better intersection.

**Two caveats to verify on your own toolchain before rollout:**

1. **Cursor CLI may not honor the compatibility paths.** A bug report from March 2026 says `.claude/skills/` loads in the Cursor IDE but not in the Cursor CLI. If your workflow uses `cursor-agent` in CI, confirm this before relying on it, and set `skills_dir: .cursor/skills` with a second dest if it still reproduces.
2. **Nested scoping is documented for `.cursor/skills/` and `.agents/skills/`.** Cursor scopes skills found under a nested project directory to files inside that directory. Whether the same scoping applies to the compatibility paths is not stated in the docs. If `infra/.claude/skills/` turns out to load globally rather than scoped to `infra/`, the cost is wasted context rather than a broken build, but confirm it before leaning on nested placement.

Acceptance criterion 18 exists to force this check rather than leaving it to discovery in production.

#### 5.7.2 The `AGENTS.md` managed block

`AGENTS.md` is hand-owned. Sync manages exactly one delimited block inside it and never touches anything else in the file.

```markdown
<!-- BEGIN LOADOUT: agent-rules (generated, do not edit) -->
## Agent Rules

This project's coding rules live as individual files under `.cursor/rules/`. Cursor loads
them automatically based on the scopes below. Other agents do not, so you have to load them
yourself.

Before editing files that match a rule's scope, read that rule file and follow it. These are
binding project conventions, not suggestions. Rules scoped `Always` apply to all work in this
repo, so read them at the start of a session.

| Rule | Scope | What it covers |
| --- | --- | --- |
| `.cursor/rules/commit-style.mdc` | Always | Conventional-commit format and when to split a change into multiple commits |
| `.cursor/rules/uv-workspace.mdc` | `**/pyproject.toml`, `packages/**/*.py` | UV workspace layout, dependency placement, and lockfile discipline |
| `infra/.cursor/rules/aws-conventions.mdc` | `infra/**/*.tf` | Terraform module structure, resource tagging, and state layout |

Skills are installed at `.claude/skills/`, which both Cursor and Claude Code load
automatically. You do not need to read those manually.

Managed by [loadout](https://github.com/<org>/loadout). Run `just loadout-sync` to regenerate.
Edits inside this block are overwritten.
<!-- END LOADOUT: agent-rules -->
```

Rendering contract:

- **One row per synced rule**, including rules written to nested subtrees. The `Rule` column is the path relative to the repo root, so an agent can open it directly.
- **Scope column** is `Always` when `alwaysApply: true`, otherwise the `globs` list rendered in backticks, otherwise `On request` when the rule has neither.
- **What it covers** is the rule's frontmatter `description`, verbatim. This is why lint requires it.
- **Deterministic ordering**: `Always` rules first, then the rest sorted by path. Without a fixed order the block churns on every sync and pollutes diffs.
- **Empty case**: when a project syncs zero rules, remove the block entirely rather than emitting an empty table.

Block handling:

- Sync rewrites only the span between the markers. Everything above and below is preserved byte for byte.
- If `AGENTS.md` does not exist, create it with a minimal heading and the block appended.
- If the file exists without markers, append the block at the end.
- If exactly one marker is present, or the end marker precedes the begin marker, abort with exit code 2 rather than guessing. A mangled block usually means a bad merge, and overwriting is the wrong recovery.

#### 5.7.3 Why an index instead of inlining the rules

Inlining every rule body into `AGENTS.md` would put the full text of every rule into context on every request for every agent, which is exactly the cost that Cursor's `globs` scoping exists to avoid. The index preserves conditional loading: an agent spends a few dozen tokens on the table and reads the full rule only when its scope matches the task at hand.

The tradeoff is honest and worth stating in the spec: this is a **best-effort** mechanism. A non-Cursor agent may skip a rule it should have read. The description column carries the weight, so write descriptions that state when the rule matters, not just what it is about.

### 5.8 The `CLAUDE.md` bridge

Claude Code does not read `AGENTS.md`. A repo containing only `AGENTS.md` gives Claude Code zero project instructions, with no error and no warning. Anthropic's documented workaround is an `@` import from `CLAUDE.md`, which Claude Code expands at session start as if the imported content were inline.

Sync therefore manages a second, much smaller block at the top of `CLAUDE.md`:

```markdown
<!-- BEGIN LOADOUT: agents-import (generated, do not edit) -->
@AGENTS.md
<!-- END LOADOUT: agents-import -->
```

Same handling rules as 5.7.2. If `CLAUDE.md` does not exist, create it containing only this block. If it exists, insert the block at the top and preserve the rest, so Claude-specific instructions a developer added below continue to work.

The import is used rather than `ln -s AGENTS.md CLAUDE.md` because symlinks do not survive every checkout, and because the import leaves `CLAUDE.md` as a real file that can still hold Claude-only overrides below the block.

Set `claude_bridge: false` in the manifest to skip this block.

### 5.9 Hooks

Hooks are deterministic scripts that run at agent lifecycle events. Unlike skills, Cursor and Claude Code use different config formats and discovery paths:

| Tool | Config | Scripts |
| --- | --- | --- |
| Cursor | `.cursor/hooks.json` | conventionally `.cursor/hooks/` |
| Claude Code | `.claude/settings.json` (`hooks` key) | any path the config points at |

Cursor can also load Claude Code hooks from `.claude/settings.json` when third-party compatibility is enabled, but cloud agents look for `.cursor/hooks.json`, and Claude Code does not read Cursor's format. So sync:

1. **Stores scripts once** under `.cursor/hooks/<name>/` (Cursor-native; prioritized).
2. **Writes `.cursor/hooks.json`** registering Cursor events (for `deny-dangerous`, `beforeShellExecution`).
3. **Writes `.claude/settings.json`** registering Claude events (for `deny-dangerous`, `PreToolUse` / `Bash`) that point at the same `.cursor/hooks/` scripts.

Neither harness sees two copies of the script. Cursor with third-party Claude hooks enabled may run both registrations for a shell command; the deny guard is idempotent. Other Claude project settings belong in `.claude/settings.local.json` — loadout owns `.claude/settings.json` when hooks are selected.

#### 5.9.1 Hook directory

```
hooks/deny-dangerous/
├── hook.yaml                 # REQUIRED. Registration metadata (not vendored)
├── deny-dangerous.sh         # Script; understands Cursor and Claude payloads
├── dangerous-patterns.txt    # Supporting denylist
└── test-guard.sh             # Author/verification harness (vendored)
```

`hook.yaml` contract:

- Required keys: `name`, `description`, `script`, `cursor` (`event`, optional `args`), `claude` (`event`, `matcher`).
- `name` must equal the containing directory name.
- `script` must exist in the hook directory.
- Sync excludes `hook.yaml` from the project copy (metadata only).

#### 5.9.2 Default destinations and generated configs

- Default hook dest: `.cursor/hooks/<dirname>`
- Generated Cursor config src recorded as `__generated__/cursor/hooks.json`
- Generated Claude config src recorded as `__generated__/claude/settings.json`

---

## 6. CLI behavior

Package name `loadout`. Invoked from a project via `uvx`, so no global install is needed:

```
uvx --from git+<loadout>@<ref> loadout <command>
```

### `loadout sync`

1. Read and validate `.loadout.yaml`.
2. If `.loadout.lock` exists and its `ref` matches the manifest, fetch the loadout repo at the locked `resolved_sha`. Otherwise resolve `ref` to a SHA.
3. Resolve loadouts depth-first, apply `include`, then apply `exclude`.
4. Validate: unmatched selectors, `dest` collisions, missing `src`, malformed rule frontmatter, and the full skill contract from 5.2.2 and 5.2.3 (`SKILL.md` present at the skill root, frontmatter keys allowed, `name` matching the directory, `dest` basename matching `src` basename). Any failure aborts before writing.
5. Compute the destination set. Delete any file under a managed destination that is present in the old lockfile but not in the new set (prune). Never delete a file that is not listed in the old lockfile.
6. Write files with headers.
7. Render and write the managed blocks in `AGENTS.md` and `CLAUDE.md` (5.7, 5.8).
8. Write the lockfile, including `managed_blocks` hashes.
9. Print a summary: added, updated, removed, unchanged, plus whether either managed block changed.

Sync is idempotent. Running it twice at the same ref produces no diff.

### `loadout sync --check`

Same resolution, no writes. Exit 1 if the on-disk file set, any file hash, or either managed block differs from the lockfile. Content outside the block markers is ignored entirely. This catches hand-edits to generated files, a stale `AGENTS.md` table, and a bumped `ref` that was not re-synced. Intended for CI.

### `loadout update [--to <ref>]`

Resolve the latest release tag (or the given ref), rewrite `ref` in the manifest, run a full sync, print the `CHANGELOG.md` entries between the old and new version.

### `loadout init --loadouts a,b`

Write a starter manifest. Used by the cookiecutter hook.

### Local development override

If `LOADOUT_PATH` is set, read the loadout repo from that local directory instead of cloning. The lockfile then records `"resolved_sha": "local"` and `sync --check` warns rather than failing on SHA mismatch. Required for offline generation, loadout repo development, and template tests.

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success, or `--check` clean |
| 1 | `--check` found drift |
| 2 | Validation error (bad manifest, unmatched selector, collision) |
| 3 | Network or auth failure fetching the loadout repo |

---

## 7. `just` recipes

All commands are `just` recipes. No bash scripts, no Makefiles.

### 7.1 Loadout repo `justfile`

```just
set shell := ["bash", "-uc"]

default:
    @just --list

# Validate every rule, skill, and loadout definition in this repo
lint:
    uv run loadout lint

# Run the test suite
test:
    uv run pytest

# Tag and push a release. usage: just release 1.5.0
release version:
    #!/usr/bin/env bash
    set -euo pipefail
    grep -q "## {{version}}" CHANGELOG.md || { echo "no CHANGELOG entry for {{version}}"; exit 1; }
    just lint && just test
    git tag -a "v{{version}}" -m "v{{version}}"
    git push origin "v{{version}}"

# Sync a local project against this working copy, for loadout repo development
try project:
    LOADOUT_PATH="$(pwd)" just -f "{{project}}/justfile" loadout-sync
```

`loadout lint` must verify:

- Every rule parses, with valid frontmatter, a non-empty `description`, and no `alwaysApply: true` outside `rules/core/`. The description is not optional: it is the only thing a non-Cursor agent sees in the `AGENTS.md` index.
- Every skill satisfies the frontmatter contract in 5.2.2, including `name` matching its directory.
- No stray `SKILL.md` below a skill root. A supporting doc must live in `references/` under a different filename, or it will be discovered as a separate skill.
- Every path in `evals[].files` exists.
- Every loadout resolves, with no `extends` cycles and no `dest` collisions.
- No orphan files: present in `rules/` or `skills/` but referenced by no loadout.

Warn, but do not fail, when `SKILL.md` exceeds 500 lines or a `references/` file exceeds 300 lines without a table of contents. These are budget signals, not errors.

### 7.2 Project `justfile` (generated by the template)

```just
source_ref := `grep '^ref:' .loadout.yaml | awk '{print $2}'`
source_url := `grep '^source:' .loadout.yaml | awk '{print $2}'`
loadout := "uvx --from git+" + source_url + "@" + source_ref + " loadout"

# Apply the pinned rules and skills to this repo
loadout-sync:
    {{loadout}} sync

# Fail if .cursor/ does not match the lockfile
loadout-check:
    {{loadout}} sync --check

# Bump to the latest release and re-sync
loadout-update:
    {{loadout}} update

# List what the current manifest resolves to
loadout-list:
    {{loadout}} resolve --list
```

---

## 8. Cookiecutter integration

### 8.1 Hook responsibilities

The post-generation hook is a **thin caller**. It must not contain copying logic. Day-0 generation and day-100 updates run the same code path.

`hooks/post_gen_project.py`:

1. Map cookiecutter answers to loadout names.
2. Write `.loadout.yaml`.
3. Run `just loadout-sync`.
4. On success, `git add` the generated `.cursor/` output as part of the initial commit.

### 8.2 Answer to loadout mapping

Answers select **loadout names only**, never file lists. What a loadout contains stays versioned in the loadout repo, so loadouts can be improved without touching the template.

```python
LOADOUTS = ["base", "python-monorepo"]

if ctx["use_terraform"] == "yes":
    LOADOUTS.append("aws-terraform")
if ctx["use_playwright"] == "yes":
    LOADOUTS.append("playwright-e2e")
```

Keep this mapping coarse and stable. Already-generated projects receive changes to loadout *contents* but never to this mapping, so most improvements should land as content changes inside an existing loadout.

### 8.3 Hook must never hard-fail

**Cookiecutter deletes the entire output directory if a post-gen hook exits nonzero.** A network blip, an expired token, or a corporate proxy would destroy the freshly generated project.

Required behavior: catch every exception from the sync step, print a clear warning naming `just loadout-sync` as the fix, leave `.loadout.yaml` in place, and exit 0.

```python
try:
    subprocess.run(["just", "loadout-sync"], check=True)
except Exception as exc:
    print(f"WARNING: could not sync rules and skills: {exc}")
    print("Project generated successfully. Run `just loadout-sync` when you have network access.")
```

### 8.4 Determinism

The hook resolves the pinned ref to a SHA and records it in the lockfile before finishing. Two projects generated a week apart from the same template commit must contain identical `.cursor/` content.

Template tests set `LOADOUT_PATH` to a checked-out loadout repo fixture so generation is offline and hermetic.

### 8.5 Use `cruft`, not raw cookiecutter

`cruft` records the template commit in the generated project and provides `cruft update`. That covers template drift. `loadout update` covers loadout repo drift. Keep the two update paths in separate PRs so the diffs stay readable.

---

## 9. Change propagation

Nothing updates automatically. A project picks up loadout repo changes only when its `ref` is bumped and sync is re-run, which produces a reviewable diff in `.cursor/`.

Three trigger paths:

1. **Manual.** A developer runs `just loadout-update`.
2. **Scheduled bot.** A weekly workflow in each project runs `just loadout-update` and opens a PR titled with the changelog delta. This is the workhorse. Model it on Dependabot: many small reviewable PRs beat one large drift event.
3. **Fan-out on release.** The loadout repo's release workflow sends `repository_dispatch` to consumer repos. Discover consumers by GitHub topic (`loadout-consumer`), not a hardcoded list in the loadout repo, which goes stale.

Rollout discipline: bump one representative project first, live with it for a few days, then dispatch to the rest. Agent instruction changes are hard to evaluate in review and easy to evaluate in use.

### 9.1 Versioning policy

| Bump | When |
| --- | --- |
| Patch | Wording, clarification, typo |
| Minor | New rule, new skill, new loadout, additive change to a loadout |
| Major | Rename or removal of any `src` path, loadout removal, manifest schema change |

Any change that could invalidate a project's `exclude` selector is major.

---

## 10. CI

### Loadout repo

- `just lint` and `just test` on every PR.
- A matrix job that resolves every loadout and asserts it produces a valid, collision-free file set.
- A job asserting no vendored output would contain an `evals/` directory or a `*-workspace/` directory.
- Block release tags if `CHANGELOG.md` has no entry for the version.

Skill evals run in the loadout repo, never in consuming projects. They are slow and non-deterministic, so run them on a schedule or on manual dispatch rather than on every PR, and treat a pass-rate regression as a signal to review rather than a hard gate.

### Project repos (generated by the template)

```yaml
- name: Verify agent rules and skills
  run: just loadout-check
```

Fails on hand-edited generated files and on a bumped ref that was not re-synced.

---

## 11. Acceptance criteria

1. `just loadout-sync` in a fresh project produces `.cursor/rules/` and `.claude/skills/` matching the manifest, plus a lockfile.
2. Running it a second time produces zero diff.
3. Removing a loadout from the manifest and re-syncing deletes the now-unselected files and leaves unrelated files untouched.
4. An `exclude` entry that matches no file at the pinned ref fails with exit code 2 and a message naming the stale selector.
5. Two loadouts targeting the same `dest` with different `src` fails with exit code 2.
6. Editing a generated file by hand makes `just loadout-check` exit 1.
7. Bumping `ref` without syncing makes `just loadout-check` exit 1.
8. With the network unreachable, cookiecutter generation still succeeds, the project directory survives, and a warning names `just loadout-sync`.
9. With `LOADOUT_PATH` set, sync uses the local loadout and never touches the network.
10. Terraform rules land only under `infra/.cursor/`, and Playwright rules only under `tests/e2e/.cursor/`, for a project that selected those loadouts.
11. A project generated without `aws-terraform` contains no Terraform rule or skill anywhere under `.cursor/` or `.claude/`, and no Terraform row in the `AGENTS.md` block.
12. Syncing a skill that has `scripts/`, `references/`, `assets/`, and `agents/` reproduces the full subtree, with scripts still executable and binary assets byte-identical to the loadout repo.
13. That same sync produces no `evals/` directory in the project, and the lockfile lists a hash for every copied file in the subtree.
14. Hand-editing a copied `scripts/*.py` makes `just loadout-check` exit 1.
15. A loadout skill whose frontmatter `name` does not match its directory name fails `just lint` and fails `sync` with exit code 2.
16. A loadout that relocates a skill to a nested `dest` but renames its basename fails with exit code 2.
17. Skills land in `.claude/skills/` and nowhere else. No `.agents/skills/` or `.cursor/skills/` directory is created.
18. A skill synced to `.claude/skills/` is discovered by both Cursor and Claude Code in a manual smoke test. Verify this once on the real toolchain before rollout, per the caveats in 5.7.1.
19. Setting `skills_dir: .agents/skills` relocates skills on the next sync and prunes the old location.
20. `AGENTS.md` gains an Agent Rules block listing every synced rule with its path, scope, and description, including rules written to nested subtrees.
21. Hand-written content above and below the block survives a re-sync byte for byte, and re-running sync produces no diff in the block.
22. Removing the last rule from the manifest removes the block entirely rather than leaving an empty table.
23. A file with a begin marker and no end marker fails with exit code 2 and does not overwrite the file.
24. `CLAUDE.md` contains the `@AGENTS.md` import block at the top, with any pre-existing Claude-specific content preserved below it.
25. A rule whose frontmatter has no `description` fails `just lint`, since it would render a blank cell in the index.

---

## 12. Out of scope

- Publishing to the Cursor Marketplace as a plugin.
- Translating `.mdc` rules into native rule formats for other agents. Rules stay Cursor-native files, surfaced to everyone else through the `AGENTS.md` index (5.7).
- Writing skills to more than one directory. Revisit only if a third agent that reads neither `.claude/skills/` nor `.cursor/skills/` enters the workflow, in which case set `skills_dir` or add a second dest.
- Per-developer personal rules. Those belong in `~/.cursor/`, outside this system.
- Automatic merging of local edits to generated files. Generated files are read-only by convention and enforced by `loadout-check`.

## 13. Implementation notes

- Fetch the loadout repo with a shallow clone into a temp dir, or a tarball fetch if the host supports it. Cache by SHA under the user cache dir so repeated syncs across projects are fast.
- Write files atomically (temp file, then rename) so an interrupted sync cannot leave a half-written rule in place.
- Preserve the executable bit on scripts inside skill directories.
- Authoring a skill with Claude Code's `skill-creator` produces a directory that drops into `skills/` unchanged. The only requirement this repo adds is that its `evals/` sits at the skill root so sync's exclusion rule finds it, which is where `skill-creator` already puts it.
- Render managed blocks to a string, compare to what is on disk, and skip the write when identical. This keeps file mtimes stable and avoids noisy diffs.
- Local Cursor sessions may need a window reload to notice newly synced files. Claude Code picks up skill changes within a session but needs a restart if the skills directory did not exist at launch. Mention both in the sync summary output.
