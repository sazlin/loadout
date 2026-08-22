<p align="center">
  <img src="docs/assets/loadout-banner.jpg" alt="Cute lo-fi beaver in safety goggles packing a LOADOUT toolbox in a busy workshop with clustered hand tools" width="100%" />
</p>

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
uvx --from git+https://github.com/sazlin/loadout@main loadout init --loadouts base,python
```

**2. Sync** — vendor rules, skills, agents, hooks, and MCP configs into the repo:

```bash
uvx --from git+https://github.com/sazlin/loadout@main loadout sync
```

**3. Commit the result** — teammates and CI get the same files with no extra setup:

```bash
git add .loadout.yaml .loadout.lock .cursor .claude .mcp.json
git status   # also stage AGENTS.md / CLAUDE.md if sync touched them
git commit -m "Add loadout-managed agent tooling"
```

Pin a release tag instead of `main` once you want a fixed upgrade cadence:

```bash
uvx --from git+https://github.com/sazlin/loadout@v0.5.0 loadout sync
```

`init` writes a starter `.loadout.yaml` like:

```yaml
source: https://github.com/sazlin/loadout
ref: main
loadouts:
  - base
  - python
```

## Change selected loadouts

Edit `.loadout.yaml` — the `loadouts:` list is the only control surface you need day to day.

```yaml
source: https://github.com/sazlin/loadout
ref: main
loadouts:
  - base
  - python
  - terraform   # add
  # - aws       # remove by deleting the line
```

Then re-sync and commit the diff:

```bash
uvx --from git+https://github.com/sazlin/loadout@main loadout sync
# or, if your project justfile has the consumer recipes:
just loadout-sync
```

Preview what a manifest resolves to before writing:

```bash
uvx --from git+https://github.com/sazlin/loadout@main loadout resolve --list
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
uvx --from git+https://github.com/sazlin/loadout@main loadout update
# or: just loadout-update
```

`update` rewrites `ref:` to the latest release tag (or `--to vX.Y.Z`), re-runs `sync`, and prints the CHANGELOG entries that landed.

**Manual alternative:**

```yaml
# .loadout.yaml
ref: v0.5.0   # was: main or an older tag
```

```bash
uvx --from git+https://github.com/sazlin/loadout@v0.5.0 loadout sync
```

Commit `.loadout.yaml`, `.loadout.lock`, and the generated tree so the upgrade is reviewable in PRs.

## Check for drift

Fail CI (or a local check) if someone hand-edited vendored files or the lock is stale:

```bash
uvx --from git+https://github.com/sazlin/loadout@main loadout sync --check
# or: just loadout-check
```

Example GitHub Actions step:

```yaml
- name: Verify agent rules and skills
  run: just loadout-check
```

## Available loadouts

| Loadout | Extends | What you get |
| --- | --- | --- |
| `base` | — | Core conventions (including ready-for-review PRs, never drafts), release checklist, anti-sleep, session decision-review and `/learn` skills, deny-dangerous hook, davinci, Context7 and Linear MCPs |
| `python` | `base` | Python code style + pytest rules, python_coder agent |
| `python-monorepo` | `python` | UV workspace rules |
| `db` | `base` | Alembic `db-migrations` skill |
| `github` | `base` | GitHub PR media attach (`github-upload-media-to-pr`) |
| `typescript` | `base` | TypeScript code style rules |
| `terraform` | `base` | Terraform/AWS conventions (scoped under `infra/`) + plan-review skill |
| `aws` | `base` | AWS Knowledge MCP |
| `supabase` | `db` | Vendored Supabase `postgres-best-practices` skill (query, connections, RLS, schema) plus inherited `db-migrations` |
| `playwright` | `base` | Playwright Test Agents (planner, generator, healer), `playwright-cli`, plan-generate-heal skill, and dest-scoped `e2e/` conventions |
| `playwright-e2e` | `playwright` | Compatibility alias of `playwright` |
| `agents` | `base` | Named loadout (not the `agents/` directory): LangChain docs MCP + refining-evals skill |
| `superpowers` | — | Opt-in Superpowers skills + SessionStart hook (see [warnings](#notes-and-warnings)) |
| `pr_review` | — | PR-review harness: dimensional reviewers, orchestrator, issue_resolver, verifier, risk_classifier, slash-command skills, and honor-check-intent rule |

Compose freely — for example `base,python-monorepo,terraform` or `base,typescript,playwright`. This repository dogfoods `base` and `pr_review` (see `.loadout.yaml`).

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
agents and for imported ones. Underscore-prefixed files are templates or notes,
not agents: lint, orphan checks, and sync skip them. Markdown under `evals/`
is not an agent.

**Two families.**

| Family | Files | Loadout | Role |
| --- | --- | --- | --- |
| Implementation | `python_coder`, `davinci`, `playwright_planner`, `playwright_generator`, `playwright_healer` | `python`, `base`, `playwright` | Edit a scoped change set and emit a JSON report with `changes` / `verification` |
| PR review harness | `review_correctness`, `review_maintainability`, `review_scale`, `review_security`, `review_orchestrator`, `issue_resolver`, `verifier`, `risk_classifier` | `pr_review` | Panel review, task resolution, sequential `VERIFIERS.md` claims, and low-risk squash merge. Opt in with `loadouts: [base, pr_review]`. |

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
the LangChain docs MCP plus the vendored `refining-evals` skill:

```yaml
loadouts: [agents]
```

## Manifest cheatsheet

| Field | Required | Purpose |
| --- | --- | --- |
| `source` | yes | Loadout git URL (default: this repo) |
| `ref` | yes | Branch or tag pin (`main`, `v0.5.0`, …) |
| `loadouts` | yes | Named loadouts to compose |
| `include` / `exclude` | no | Extra / removed paths after composition |
| `skills_dir` / `hooks_dir` / `agents_dir` | no | Override sync destinations |

Full format: [loadout-spec.md](loadout-spec.md).

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
just release 0.3.0   # on release/v0.3.0: validate, push, open PR; CI tags on merge

# Import a third-party skill into skills/ (then wire it into a loadout YAML)
just add_skill mattpocock/skills --skill grill-me
```

Repo-local skills for work *on this repository* live under `.claude/skills/`
(committed). `skill-security-check` audits candidate skills before they land
in `skills/` (not part of any consumer loadout). `refining-evals` is also
vendored on the `agents` loadout; see [Agents](#agents).

## Documentation

- [loadout-spec.md](loadout-spec.md) — full specification (agents: section 5.10)
- [agents/_agent_template.md](agents/_agent_template.md) — authoring skeleton
- [agents/](agents/) — agent definitions plus colocated `evals/`
- [docs/consumer-contract.md](docs/consumer-contract.md) — cookiecutter hook and project `justfile` contract
- [CHANGELOG.md](CHANGELOG.md) — release notes

## License

[MIT](LICENSE) © Sean Azlin
