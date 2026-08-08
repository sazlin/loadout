# Release Branch Tagging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require releases on `release/vX.Y.Z` branches and auto-tag merge commits on `main`/`master` via CI.

**Architecture:** Update `skills/release-checklist` and rewrite `just release` as a push+PR helper (no local tags). Add `.github/workflows/tag-release.yml` that parses the merged PR head branch, validates versions, and creates an annotated `vX.Y.Z` tag on the merge commit.

**Tech Stack:** Just recipes, GitHub Actions, `gh` CLI, existing CHANGELOG/`pyproject`/`__version__` conventions.

## Global Constraints

- Branch names must be exactly `release/vX.Y.Z` (with `v` prefix).
- Tags are annotated `vX.Y.Z` only; no GitHub Release objects.
- `just release` never creates the branch, never tags, never pushes tags.
- Keep `.github/workflows/ci.yml` unchanged.
- Always branch from `main`/`master` for this work (already on `feature/release-branch-tagging`).

---

### Task 1: Update release-checklist skill

**Files:**
- Modify: `skills/release-checklist/SKILL.md`
- Modify: `CHANGELOG.md` (Unreleased bullet)

**Interfaces:**
- Consumes: design in `docs/superpowers/specs/2026-08-07-release-branch-tagging-design.md`
- Produces: skill steps agents must follow for branch/PR/CI-tag releases

- [ ] **Step 1: Rewrite SKILL.md** to the 8-step checklist from the design (dedicated `release/vX.Y.Z` branch, no local tags, CI owns tagging, rollback via previous pin).

- [ ] **Step 2: Add Unreleased CHANGELOG bullet** describing the release-branch + CI tagging workflow for consumers/agents.

- [ ] **Step 3: Commit**

```bash
git add skills/release-checklist/SKILL.md CHANGELOG.md
git commit -m "feat: require release/v* branches in release-checklist"
```

---

### Task 2: Rewrite `just release` + README

**Files:**
- Modify: `justfile` (`release` recipe)
- Modify: `README.md` (Loadout repo commands one-liner)
- Optionally align: `loadout-spec.md` release recipe docs if they still show local tagging

**Interfaces:**
- Consumes: current branch must be `release/v{{version}}`; CHANGELOG `## {{version}}`; pyproject/`__version__` == version
- Produces: pushed branch + `gh pr create` (or existing PR URL); no tags

- [ ] **Step 1: Replace `release` recipe** with validation → lint/test → push → `gh pr create` per design. Resolve default branch as `main` if it exists remotely, else `master`.

- [ ] **Step 2: Update README** one-liner to: requires being on `release/vX.Y.Z`; pushes and opens PR; CI tags on merge.

- [ ] **Step 3: Update loadout-spec.md** release snippet if present so it does not instruct local tagging.

- [ ] **Step 4: Smoke-check recipe syntax**

Run: `just --list` and `bash -n` on the embedded script if practical; do not push a real release.

- [ ] **Step 5: Commit**

```bash
git add justfile README.md loadout-spec.md
git commit -m "feat: make just release open a PR instead of tagging"
```

---

### Task 3: Add tag-release GitHub workflow

**Files:**
- Create: `.github/workflows/tag-release.yml`

**Interfaces:**
- Consumes: merged PR with `head_ref` matching `^release/v[0-9]+\.[0-9]+\.[0-9]+$`
- Produces: annotated tag `v$VERSION` on merge commit SHA (idempotent skip if exists)

- [ ] **Step 1: Add workflow** with `pull_request` closed on `main`/`master`, job guards, version parse, CHANGELOG/pyproject/`__version__` checks, idempotent tag create+push, `contents: write`.

- [ ] **Step 2: Static review** — confirm `ci.yml` untouched; regex and skip behavior match the design.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/tag-release.yml
git commit -m "ci: tag merge commits from release/v* PRs"
```

---

### Task 4: Verify and finish

**Files:** none required beyond fixes

- [ ] **Step 1: Run** `just lint && just test`

- [ ] **Step 2: Confirm** `justfile` release recipe no longer contains `git tag`

- [ ] **Step 3: Use finishing-a-development-branch** — present PR/merge options to the user
