<!-- generated:optional:banner:start -->
<p align="center">
  <img src="docs/assets/loadout-banner.jpg" alt="Cute lo-fi beaver in safety goggles packing a LOADOUT toolbox in a busy workshop with clustered hand tools" width="100%" />
</p>
<!-- generated:optional:banner:end -->

# Loadout

[![CI](https://github.com/sazlin/loadout/actions/workflows/ci.yml/badge.svg)](https://github.com/sazlin/loadout/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/sazlin/loadout?sort=semver)](https://github.com/sazlin/loadout/releases)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![uv](https://img.shields.io/badge/runner-uv%20%2F%20uvx-de5fe9)](https://docs.astral.sh/uv/)

**Sean's personal skills, agents, hooks, and MCP configs centralized and categorized into project-deployable "loadouts".**

## The Gist
- Everything is highly opinionated and changing constantly.
- Everything is "Cursor-first, Claude compatible" because those are the harnesses I use at the moment (Pi coming next).
- Why did I make this? Loadout is a critical piece of my in-progress software metafactory, which I use to bootstrap new software factories for startups. Loadout is what my metafactory uses to equip each factory's project with exactly the right rules, skills, agents, etc.
- Loadouts are "vendored" / copied into projects w/ metadata enabling intelligent updates at the project level. Similarly, 3rd party skills are vendored into this Loadout repo (and vetted with a skill screener). Everything is optimized for stability and security; loadouts only have skills and agents that were expicitly installed and screened, and projects only get exactly those screened versions.
- Loadouts are incomplete. I'm still generalizing and migrating project-specific skills and agents into this project. More is coming.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) (for `uvx`). Run these from any project directory.

**1. Initialize a manifest** — choose the loadouts you want:

```bash
uvx --from git+https://github.com/sazlin/loadout@v0.15.0 loadout init --loadouts base,python
```

**2. Sync** — vendor rules, skills, agents, hooks, and MCP configs into the repo:

```bash
uvx --from git+https://github.com/sazlin/loadout@v0.15.0 loadout sync
```

**3. Commit the result** — teammates and CI get the same files with no extra setup:

```bash
git add .loadout.yaml .loadout.lock .cursor .claude .mcp.json
git status   # also stage AGENTS.md / CLAUDE.md if sync touched them
git commit -m "Add loadout-managed agent tooling"
```

Pin a release tag instead of `main` once you want a fixed upgrade cadence:

```bash
uvx --from git+https://github.com/sazlin/loadout@v0.15.0 loadout sync
```

`init` writes a starter `.loadout.yaml` like:

```yaml
source: https://github.com/sazlin/loadout
ref: v0.15.0
loadouts:
  - base
  - python
```

## Change selected loadouts

Edit `.loadout.yaml` — the `loadouts:` list is the only control surface you need day to day.

```yaml
source: https://github.com/sazlin/loadout
ref: v0.15.0
loadouts:
  - base
  - python
  - terraform   # add
  # - aws       # remove by deleting the line
```

Then re-sync and commit the diff:

```bash
uvx --from git+https://github.com/sazlin/loadout@v0.15.0 loadout sync
# or, if your project justfile has the consumer recipes:
just loadout-sync
```

Preview what a manifest resolves to before writing:

```bash
uvx --from git+https://github.com/sazlin/loadout@v0.15.0 loadout resolve --list
# or: just loadout-list
```

Optional fine-tuning (rarely needed):

```yaml
include:
  - rules/core/commit-style.mdc
exclude:
  - skills/release-checklist
```

## Pull loadout changes over time

When this repo ships new rules/skills (or you want a newer pin), bump the manifest ref and re-sync.

**Recommended — one command:**

```bash
uvx --from git+https://github.com/sazlin/loadout@v0.15.0 loadout update
# or: just loadout-update
```

`update` rewrites `ref:` to the latest release tag (or `--to vX.Y.Z`), re-runs `sync`, and prints the CHANGELOG entries that landed.

**Manual alternative:**

```yaml
# .loadout.yaml
ref: v0.15.0   # was: main or an older tag
```

```bash
uvx --from git+https://github.com/sazlin/loadout@v0.15.0 loadout sync
```

Commit `.loadout.yaml`, `.loadout.lock`, and the generated tree so the upgrade is reviewable in PRs.

## Check for drift

Fail CI (or a local check) if someone hand-edited vendored files or the lock is stale:

```bash
uvx --from git+https://github.com/sazlin/loadout@v0.15.0 loadout sync --check
# or: just loadout-check
```

Example GitHub Actions step:

```yaml
- name: Verify agent rules and skills
  run: just loadout-check
```

<!-- generated:optional:loadouts-section:start -->
## Available loadouts

<!-- generated:loadouts-catalog:start -->
| Loadout | Extends | Agents | Skills | Rules | MCPs | Hooks | CLI Tools |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `base` | — | <ul><li><a href="agents/davinci/davinci.md"><code>davinci</code></a></li></ul> | <ul><li><a href="skills/anti-sleep/SKILL.md"><code>anti-sleep</code></a></li><li><a href="skills/decisions/SKILL.md"><code>decisions</code></a></li><li><a href="skills/next-decision/SKILL.md"><code>next-decision</code></a></li><li><a href="skills/learn/SKILL.md"><code>learn</code></a></li><li><a href="skills/release-checklist/SKILL.md"><code>release-checklist</code></a></li></ul> | <ul><li><a href="rules/core/commit-style.mdc"><code>commit-style</code></a></li><li><a href="rules/core/repo-conventions.mdc"><code>repo-conventions</code></a></li><li><a href="rules/core/colocated-evals.mdc"><code>colocated-evals</code></a></li><li><a href="rules/core/no-cursor-coauthor.mdc"><code>no-cursor-coauthor</code></a></li><li><a href="rules/core/pr-ready-for-review.mdc"><code>pr-ready-for-review</code></a></li><li><a href="rules/core/readme-loadouts.mdc"><code>readme-loadouts</code></a></li><li><a href="rules/agents/agent-authoring.mdc"><code>agent-authoring</code></a></li></ul> | <ul><li><a href="mcps/context7/mcp.yaml"><code>context7</code></a></li><li><a href="mcps/linear/mcp.yaml"><code>linear</code></a></li></ul> | <ul><li><a href="hooks/deny-dangerous/hook.yaml"><code>deny-dangerous</code></a></li></ul> | — |
| `implementation_harness` | — | <ul><li><a href="agents/implementation_orchestrator/implementation_orchestrator.md"><code>implementation_orchestrator</code></a></li><li><a href="agents/implementation_planner/implementation_planner.md"><code>implementation_planner</code></a></li><li><a href="agents/implementation_plan_reviewer/implementation_plan_reviewer.md"><code>implementation_plan_reviewer</code></a></li><li><a href="agents/implementation_builder/implementation_builder.md"><code>implementation_builder</code></a></li><li><a href="agents/implementation_build_reviewer/implementation_build_reviewer.md"><code>implementation_build_reviewer</code></a></li></ul> | <ul><li><a href="skills/create-implementation-plan/SKILL.md"><code>create-implementation-plan</code></a></li><li><a href="skills/review-implementation-plan/SKILL.md"><code>review-implementation-plan</code></a></li><li><a href="skills/build-implementation-plan/SKILL.md"><code>build-implementation-plan</code></a></li><li><a href="skills/review-implementation-build/SKILL.md"><code>review-implementation-build</code></a></li></ul> | — | — | — | — |
| `pr_review_harness` | — | <ul><li><a href="agents/review_correctness/review_correctness.md"><code>review_correctness</code></a></li><li><a href="agents/review_maintainability/review_maintainability.md"><code>review_maintainability</code></a></li><li><a href="agents/review_scale/review_scale.md"><code>review_scale</code></a></li><li><a href="agents/review_security/review_security.md"><code>review_security</code></a></li><li><a href="agents/review_orchestrator/review_orchestrator.md"><code>review_orchestrator</code></a></li><li><a href="agents/issue_resolver/issue_resolver.md"><code>issue_resolver</code></a></li><li><a href="agents/verifier/verifier.md"><code>verifier</code></a></li><li><a href="agents/risk_classifier/risk_classifier.md"><code>risk_classifier</code></a></li></ul> | <ul><li><a href="skills/dispatch-panel-review/SKILL.md"><code>dispatch-panel-review</code></a></li><li><a href="skills/dedupe-and-write-tasks/SKILL.md"><code>dedupe-and-write-tasks</code></a></li><li><a href="skills/resolve-next-task/SKILL.md"><code>resolve-next-task</code></a></li><li><a href="skills/log-progress/SKILL.md"><code>log-progress</code></a></li><li><a href="skills/dispatch-verifiers/SKILL.md"><code>dispatch-verifiers</code></a></li></ul> | <ul><li><a href="rules/core/honor-check-intent.mdc"><code>honor-check-intent</code></a></li></ul> | — | — | — |
| `superpowers` | — | — | <ul><li><a href="skills/brainstorming/SKILL.md"><code>brainstorming</code></a></li><li><a href="skills/dispatching-parallel-agents/SKILL.md"><code>dispatching-parallel-agents</code></a></li><li><a href="skills/executing-plans/SKILL.md"><code>executing-plans</code></a></li><li><a href="skills/finishing-a-development-branch/SKILL.md"><code>finishing-a-development-branch</code></a></li><li><a href="skills/receiving-code-review/SKILL.md"><code>receiving-code-review</code></a></li><li><a href="skills/requesting-code-review/SKILL.md"><code>requesting-code-review</code></a></li><li><a href="skills/subagent-driven-development/SKILL.md"><code>subagent-driven-development</code></a></li><li><a href="skills/systematic-debugging/SKILL.md"><code>systematic-debugging</code></a></li><li><a href="skills/test-driven-development/SKILL.md"><code>test-driven-development</code></a></li><li><a href="skills/using-git-worktrees/SKILL.md"><code>using-git-worktrees</code></a></li><li><a href="skills/using-superpowers/SKILL.md"><code>using-superpowers</code></a></li><li><a href="skills/verification-before-completion/SKILL.md"><code>verification-before-completion</code></a></li><li><a href="skills/writing-plans/SKILL.md"><code>writing-plans</code></a></li><li><a href="skills/writing-skills/SKILL.md"><code>writing-skills</code></a></li></ul> | — | — | <ul><li><a href="hooks/session-start/SOURCE.md"><code>session-start</code></a></li></ul> | — |
| `agents` | `base` | — | <ul><li><a href="skills/refining-evals/SKILL.md"><code>refining-evals</code></a></li></ul> | <ul><li><a href="rules/agents/agent-descriptions.mdc"><code>agent-descriptions</code></a></li></ul> | <ul><li><a href="mcps/langchain-docs/mcp.yaml"><code>langchain-docs</code></a></li></ul> | — | — |
| `aws` | `base` | — | — | — | <ul><li><a href="mcps/aws-knowledge/mcp.yaml"><code>aws-knowledge</code></a></li></ul> | — | — |
| `db` | `base` | — | <ul><li><a href="skills/db-migrations/SKILL.md"><code>db-migrations</code></a></li></ul> | — | — | — | — |
| `github` | `base` | — | <ul><li><a href="skills/github-upload-media-to-pr/SKILL.md"><code>github-upload-media-to-pr</code></a></li></ul> | — | — | — | — |
| `playwright` | `base` | <ul><li><a href="agents/playwright_planner/playwright_planner.md"><code>playwright_planner</code></a></li><li><a href="agents/playwright_generator/playwright_generator.md"><code>playwright_generator</code></a></li><li><a href="agents/playwright_healer/playwright_healer.md"><code>playwright_healer</code></a></li></ul> | <ul><li><a href="skills/playwright-agents/SKILL.md"><code>playwright-agents</code></a></li></ul> | <ul><li><a href="rules/playwright/test-agents.mdc"><code>test-agents</code></a></li><li><a href="rules/playwright/e2e-conventions.mdc"><code>e2e-conventions</code></a></li></ul> | — | — | <ul><li><code>playwright-cli</code></li></ul> |
| `python` | `base` | <ul><li><a href="agents/python_coder/python_coder.md"><code>python_coder</code></a></li></ul> | — | <ul><li><a href="rules/python/python-code-style.mdc"><code>python-code-style</code></a></li><li><a href="rules/python/pytest.mdc"><code>pytest</code></a></li></ul> | — | — | — |
| `terraform` | `base` | — | <ul><li><a href="skills/terraform-plan-review/SKILL.md"><code>terraform-plan-review</code></a></li></ul> | <ul><li><a href="rules/terraform/aws-conventions.mdc"><code>aws-conventions</code></a></li></ul> | — | — | — |
| `typescript` | `base` | — | — | <ul><li><a href="rules/typescript/typescript-code-style.mdc"><code>typescript-code-style</code></a></li></ul> | — | — | — |
| `python-monorepo` | `python` | — | — | <ul><li><a href="rules/python/uv-workspace.mdc"><code>uv-workspace</code></a></li></ul> | — | — | — |
| `supabase` | `db` | — | <ul><li><a href="skills/supabase-postgres-best-practices/SKILL.md"><code>supabase-postgres-best-practices</code></a></li></ul> | — | — | — | — |
<!-- generated:loadouts-catalog:end -->

Compose freely — for example `base,python-monorepo,terraform` or `base,typescript,playwright`. This repository dogfoods `base`, `pr_review_harness`, and `playwright` (see `.loadout.yaml`).
<!-- generated:optional:loadouts-section:end -->

## Agents

Custom subagents live under `agents/<name>/`, with the definition at
`agents/<name>/<name>.md` and evals at `agents/<name>/evals/`. Sync copies each
selected definition once to `.claude/agents/<name>.md` (Cursor compatibility
path and Claude Code's project agents directory). A loadout lists the agents it
ships; files are not auto-discovered. Agent `evals/` stays in this repo and is
not vendored.

**Authoring.** Copy [`agents/_agent_template.md`](agents/_agent_template.md) to
`agents/<name>/<name>.md` (no leading underscore) and fill every section. The
Cursor rule [`rules/agents/agent-authoring.mdc`](rules/agents/agent-authoring.mdc)
(globs `agents/*/*.md`, shipped on `base`) requires that template for new
agents and for imported ones. [`rules/agents/agent-descriptions.mdc`](rules/agents/agent-descriptions.mdc)
(shipped on `agents`) limits the YAML `description` to when-to-use and
when-not-to-use signals for other agents. Underscore-prefixed files are templates or notes,
not agents: lint, orphan checks, and sync skip them. Markdown under `evals/`
is not an agent.

**Agent families.**

| Family | Files | Loadout | Role |
| --- | --- | --- | --- |
| Scoped implementation | `python_coder`, `davinci`, `playwright_planner`, `playwright_generator`, `playwright_healer` | `python`, `base`, `playwright` | Edit a scoped change set and emit a JSON report with `changes` / `verification` |
| PR review harness | `review_correctness`, `review_maintainability`, `review_scale`, `review_security`, `review_orchestrator`, `issue_resolver`, `verifier`, `risk_classifier` | `pr_review_harness` | Panel review, task resolution, sequential `VERIFIERS.md` claims, and low-risk squash merge. Opt in with `loadouts: [base, pr_review_harness]`. |
| Implementation harness | `implementation_orchestrator`, `implementation_planner`, `implementation_plan_reviewer`, `implementation_builder`, `implementation_build_reviewer` | `implementation_harness` | Lights-out plan/review and build/review loops from an approved PRD to a GitHub PR ready for `pr_review_harness`. Opt in with `loadouts: [base, implementation_harness]`. Do not start the review harness from this phase. |

Every agent uses the same heading spine (Charter through Output schema) and a
fenced JSON report. Reviewers set `readonly: true` and omit write tools.

**Evals.** Each agent's fixtures, goldens, blank transcripts, and `evals.json`
live in [`agents/<name>/evals/`](agents/). Skill evals live in
[`skills/<name>/evals/`](skills/). Pytest scorers in `tests/` load those
files. A blank `generalPurpose` transcript must fail `score_behavior`; the
custom-agent golden must pass the full scorer. Davinci also has a live
simplification harness under [`agents/davinci/evals/`](agents/davinci/evals/).
Use the `refining-evals` skill when tightening keyword splits. The
`colocated-evals` rule on `base` forbids a parallel eval tree.

**The `agents` loadout** is a named composition, not the `agents/` directory.
It extends `base` (so you already get davinci) and adds
the LangChain docs MCP, the vendored `refining-evals` skill, and
`rules/agents/agent-descriptions.mdc` (when/when-not dispatch copy for
agent `description` fields):

```yaml
loadouts: [agents]
```

## Manifest cheatsheet

| Field | Required | Purpose |
| --- | --- | --- |
| `source` | yes | Loadout git URL (default: this repo) |
| `ref` | yes | Release tag or branch pin (`v0.15.0`, …) |
| `loadouts` | yes | Named loadouts to compose |
| `include` / `exclude` | no | Extra / removed paths after composition |
| `skills_dir` / `hooks_dir` / `agents_dir` | no | Override sync destinations |

## CLI tools

A loadout can declare `cli_tools`: named, idempotent shell commands that install CLIs its skills or agents need. `loadout sync` and `loadout update` run them in the project root after writing files. Failures are printed (`loadout: cli_tools: <name>: failed (exit N)`) and do not abort the install. `loadout sync --check` validates them but does not run them.

```yaml
cli_tools:
  - name: jq
    command: command -v jq >/dev/null || brew install jq
```

`command` is a YAML string passed to `bash -c`. Quote values that YAML would otherwise treat as booleans (`true`, `false`, `yes`, `no`).

## After syncing

Rules, skills, agents, hooks, and MCP configs are files on disk. Agents do not always pick them up until reload:

- **Cursor IDE:** Command Palette → “Developer: Reload Window”. Authenticate any OAuth MCP servers under Settings → Tools & MCP if prompted.
- **Claude Code:** restart the session (or start a new one in the project root) so it rescans `.claude/skills/` and `.mcp.json`.

## Project `just` recipes

Generated / consumer projects typically wire these into their `justfile` (see [docs/consumer-contract.md](docs/consumer-contract.md)):

| Recipe | Equivalent |
| --- | --- |
| `just loadout-sync` | `loadout sync` |
| `just loadout-check` | `loadout sync --check` |
| `just loadout-update` | `loadout update` |
| `just loadout-list` | `loadout resolve --list` |

Each recipe runs `uvx` against the `source` / `ref` pinned in `.loadout.yaml`, so the CLI version matches the content version.

## Notes and warnings

<details>
<summary><strong>Superpowers loadout</strong> — do not combine with the plugin</summary>

The `superpowers` loadout is opt-in. Add it when you want the vendored
Superpowers skills and SessionStart bootstrap **without** installing the plugin:

```yaml
loadouts: [base, python-monorepo, superpowers]
```

Enable it only on machines that do **not** have the Superpowers plugin installed
for Cursor and/or Claude Code on that project. Combining plugin + loadout causes
double SessionStart bootstrap and duplicate skills. Prefer plugin **or** loadout,
not both.

</details>

## Local development

When hacking on this repo, point sync at your working copy instead of cloning from GitHub:

```bash
LOADOUT_PATH="$(pwd)" just -f /path/to/project/justfile loadout-sync
# or from a project directory:
LOADOUT_PATH=/path/to/loadout loadout sync
```

The lockfile records `"resolved_sha": "local"`.

Repo commands:

```bash
uv sync --all-extras
just lint     # validate rules, skills, hooks, agents, mcps, loadouts
just typecheck  # pyrefly static type check
just test     # pytest
just release 0.15.0   # on release/v0.15.0: validate, push, open PR; CI tags on merge

# Import a third-party skill into skills/ (then wire it into a loadout YAML)
just add_skill mattpocock/skills --skill grill-me
```

Repo-local skills for work *on this repository* live under `.claude/skills/`
(committed). `skill-security-check` audits candidate skills before they land
in `skills/` (not part of any consumer loadout). `generating-readme` refreshes
this README from its template and loadout YAML (also not a consumer skill).
`refining-evals` is also vendored on the `agents` loadout; see [Agents](#agents).

## Documentation

- [agents/_agent_template.md](agents/_agent_template.md) — authoring skeleton
- [agents/](agents/) — agent definitions plus colocated `evals/`
- [docs/consumer-contract.md](docs/consumer-contract.md) — cookiecutter hook and project `justfile` contract
- [CHANGELOG.md](CHANGELOG.md) — release notes

## License

[MIT](LICENSE) © Sean Azlin
