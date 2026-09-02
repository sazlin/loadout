# CHANGELOG

## Unreleased

- Collapse CI into two jobs: lint/test/typecheck, and one loop over every
  `loadouts/*.yaml` for resolve plus a clean sync (no per-loadout matrix).
- Rename PR review harness comment stages to Panel Review, Resolve Issues,
  Verifiers, and Risk Classification, and append Cursor Cloud dashboard
  links.
- Abort the PR review harness when the pull request is already merged:
  skip remaining work, post an abort comment, and archive child Cursor
  Cloud agents.
- Re-run `loadout sync` against latest `main` after that harness update;
  vendored files already matched (no drift).
- After all other PR-review harness tasks, `review_orchestrator` trims
  `REVIEW_HISTORY.md` entries older than 30 days.
- Hash `TASKS_TO_RESOLVE.md` with the reviewed git short SHA
  (`TASKS_TO_RESOLVE-<short-sha>.md`) and delete that file when
  `review_orchestrator` exits so it is not left to be committed.

## 0.24.0

## 0.23.0

### Readme-loadouts detach

- Detach `readme-loadouts` from all loadouts: keep it as a repo-local rule in
  `.cursor/rules/` for this source tree only; it is no longer vendored to
  consumer projects.

## 0.22.0

## 0.21.0

## 0.20.0

- Vendor `unslop` skill from [cursor/plugins](https://github.com/cursor/plugins)
  (`pstack/skills/unslop`) on the `base` loadout for AI writing cleanup.

## 0.19.0

## 0.18.0

## 0.17.0

- Style `pr_review_harness` GitHub comments as a horizontal stage table
  with bullets, plus a WARNING/CAUTION alert only when a human must act.
- Update the PR review harness GitHub Action prompt to delegate harness steps to
  `review_orchestrator` and cloud-run constraints instead of an inline numbered
  checklist.
- Add `stripe` loadout: vendors Stripe agent skills from
  [docs.stripe.com](https://docs.stripe.com/.well-known/skills/index.json)
  (`just add_skill https://docs.stripe.com`) for payments, Connect, Apps,
  Directory, Projects, docs lookup, and API upgrades. Drops unpinned
  CLI/skill installs from `stripe-best-practices`, `stripe-directory`,
  and `stripe-projects`.
- Remove the `playwright-e2e` compatibility alias. Use `playwright`.

## 0.16.0

- Split the README Available loadouts `Etc.` column into **Hooks** (hooks
  only) and **CLI Tools** (`cli_tools` names).
- Rename the `pr_review` loadout to `pr_review_harness`.
- Add `implementation_harness`: lights-out planner/builder factory with
  nested plan-review and build-review loops (max 10) that opens a GitHub
  PR ready for the separate `pr_review_harness`.
- Allow new agents `WebSearch` and `WebFetch` (agent template plus
  `implementation_harness`) so they can look up current docs and APIs.
- Stop treating repo age or size as an `implementation_harness` brief
  field; agents inspect the tree.
- Use `autonomous` in `implementation_harness` agent and skill
  descriptions; keep `lights-out` in README and loadout catalog copy.
- Add `rules/agents/agent-descriptions.mdc` to the `agents` loadout:
  agent YAML `description` fields are when-to-use / when-not-to-use
  dispatch signals for other agents.
- Give `review_correctness`, `review_security`, and `verifier` Cursor
  `computerUse` plus observation-only `npx playwright-cli` (the browser CLI
  the `playwright` loadout installs) so they can exercise a running web UI.
  They stay read-only: no write tools, no `Task` spawners, no Playwright MCP.
- Dogfood the `playwright` loadout on this repo; `.loadout.yaml` pins `main`.
- Document that `just` recipes take no file arguments and that shared
  feature branches must be fetched and rebased before push.

## 0.15.0

- Replace the `playwright` loadout's `playwright-test` MCP
  (`npx --no-install playwright run-test-mcp-server`) with a `cli_tools`
  install of `@playwright/cli@0.1.18`. Planner, generator, and healer
  explore the live app with `npx playwright-cli` and run specs with
  `npx playwright test` (no Playwright MCP).

## 0.14.0

## 0.13.0

- Add `cli_tools` on loadout YAML: named idempotent shell commands that
  `sync` and `update` run in the project root after writing files. Failures
  are printed and do not abort the install. `sync --check` does not run them.
- Add `rules/core/readme-loadouts.mdc` to `base`: when loadouts are
  added, removed, or changed, update `README.md` **Available loadouts**
  in the same change. Catalog tests fail if a loadout is missing or its
  Extends cell drifts from the YAML.
- Add `supabase` loadout: vendors
  `skills/supabase-postgres-best-practices` from
  [supabase/agent-skills](https://github.com/supabase/agent-skills)
  (`8331f91`) for Postgres query, connection, RLS, and schema guidance.
- Add `learn` to the `base` loadout: `/learn` captures obvious agent and
  subagent mistakes from the current session as project-level rules in an
  `AGENTS.md` Learnings section (create or merge/dedupe).
- Add `github` loadout: `github-upload-media-to-pr` attaches images and
  videos to a GitHub PR via Cursor Cloud `ManagePullRequest` artifact
  upload (`computerUse` / `RecordScreen` for capture). Vendored from
  jacobmassey/github-upload-media-to-pr with `agent-browser` removed.
- Add `db` loadout: owns `db-migrations` (moved off `python-monorepo`).
  `supabase` now extends `db` instead of `base`.
- Add `playwright` loadout: Playwright Test Agents (`playwright_planner`,
  `playwright_generator`, `playwright_healer`), `cli_tools` install of
  `@playwright/cli@0.1.18` (`npx playwright-cli`), `playwright-agents`
  skill, dest-scoped `e2e/` conventions, and default `testDir` `e2e/`
  (`e2e/seed.spec.ts`). `playwright-e2e` is a compatibility alias of
  `playwright`. Cookiecutter `use_playwright` maps to `playwright`.
  Planner, generator, and healer explore the live app with CLI commands
  and run specs with `npx playwright test` (no Playwright MCP).
- Remove `e2e_test_generator`; planner/generator/healer own Playwright
  coverage under `e2e/`.
- Add `rules/core/pr-ready-for-review.mdc` to `base`: agents must open
  GitHub PRs ready for review (never as drafts). If the change is not
  ready, do not open a PR; ask the user what is blocking.

## 0.12.0

- Add `rules/core/no-cursor-coauthor.mdc` to `base`: never include Cursor as
  a git commit co-author (`Co-authored-by`, `--trailer`, or templates).

## 0.11.0

- Add `decisions` and `next-decision` to the `base` loadout: `/decisions`
  lists this session's choices as chronological grok-lines; `/next-decision`
  (optional id) reviews the next listed choice in full.
- Add `anti-sleep` to the `base` loadout: a `/anti-sleep` skill and
  `keep-awake` helper that hold a session-long `caffeinate -i` assertion
  so local Mac agents survive idle sleep during long waits and polling.

## 0.10.0

## 0.9.0

- Add a `VERIFIERS.md` claim that newly added tests targeting new behavior
  fail on the base commit and pass on the branch.

## 0.8.0

- Dogfood `base` and `pr_review` on this repo (`.loadout.yaml` pins `v0.7.0`)
  and vendor the synced agents, skills, rules, hooks, and MCP configs.
- Add a GitHub Action that launches `review_orchestrator` via the Cursor
  Cloud Agents API when a pull request is opened (`CURSOR_API_KEY` secret).
- Include `pr_review` in the CI resolve/sync matrix.
- Add `VERIFIERS.md` with a TypeScript `any` claim plus a second claim that
  files are not renamed or given a different extension to bypass checks.
- Restore the verifier eval `bad.ts` fixture (generic identity, no `any`)
  so project `VERIFIERS.md` passes without a filename workaround.
- Add `rules/core/honor-check-intent.mdc` to `pr_review`: do not rename,
  change a file extension, or move a file to work around a failing rule,
  verifier, test, or CI check when a legitimate fix exists.

## 0.7.0

- Add standalone `pr_review` loadout: move dimensional review agents off
  `base`, rewrite `review_orchestrator` as a Review → Verification → Decision
  loop, and add `issue_resolver`, `verifier`, and `risk_classifier`. Skills:
  `dispatch-panel-review`, `dedupe-and-write-tasks`, `resolve-next-task`,
  `log-progress`, `dispatch-verifiers`. Runtime files: `TASKS_TO_RESOLVE.md`
  and `REVIEW_HISTORY.md`. `VERIFIERS.md` is an optional project-owned
  true/false checklist (missing = empty list). `risk_classifier` may
  `gh pr merge --squash` for low-risk diffs after required checks are green
  (never `--admin`).
- Add `rules/core/colocated-evals.mdc` to `base` so agent and skill evals
  stay in `agents/<name>/evals/` or `skills/<name>/evals/`.
- Expand `review_orchestrator` to accept a GitHub pull request as the change
  set and post one new well-formatted PR comment per run (`gh pr comment`,
  never `--edit-last`).
- Add `mcps/linear` (`https://mcp.linear.app/mcp`) to the `base` loadout.

- Nest each agent under `agents/<name>/` with definition `agents/<name>/<name>.md`
  and colocated `evals/` (keyword fixtures, goldens, blank runs, and davinci's
  live harness). Remove `tests/evals/` and top-level `evals/`. Sync still
  vendors only the markdown definition to `.claude/agents/<name>.md`.

- Add `agents/_agent_template.md` as the authoring skeleton. Underscore-prefixed
  files under `agents/` are not agents (lint, orphan checks, and sync skip them).
- Add `rules/agents/agent-authoring.mdc` (globs `agents/*/*.md`) so new and
  imported agents follow the template. Included in the `base` loadout.
- Align `davinci` and `e2e_test_generator` output-schema closers with the
  template; assert every agent file uses the template heading order.
- Add implementation-agent evals for `python_coder`, `davinci`, and
  `e2e_test_generator` under `agents/<name>/evals/`, with
  frozen blank transcripts that fail `score_behavior`.
- Document how agents are organized in the README (template, loadouts, evals).

- Add four dimensional review agents (`review_correctness`,
  `review_maintainability`, `review_scale`, `review_security`) and
  `review_orchestrator` (now shipped on `pr_review`). The orchestrator
  launches the four reviewers in parallel, dedupes findings, and writes
  1–3-issue tasks to `TASKS_TO_RESOLVE.md`.
- Add eval fixtures and a scorer under `agents/<name>/evals/` so each
  reviewer's core checks (and the orchestrator's grouping rules) can be
  verified without implementing the fixes.
- Tighten review-agent evals so a blank general-purpose reviewer fails
  `score_behavior` (out-of-dimension bait) while custom-agent goldens still
  pass. Frozen blank transcripts live in `agents/<name>/evals/blank_runs/`.
- Add repo-local skill `.claude/skills/refining-evals` for proving an eval
  fails a blank reviewer and passes the custom agent (Ralph loop, max 5).
- Vendor `skills/refining-evals` and attach it to the `agents` loadout.

## 0.6.0

- Split `aws-terraform` into separate `aws` and `terraform` loadouts
- Add `mcps/aws-knowledge` pointing at https://knowledge-mcp.global.api.aws and
  include it in the `aws` loadout

## 0.5.0

- Add `mcps/context7` pointing at https://mcp.context7.com/mcp and include it
  in the `base` loadout

## 0.4.0

- Add loadout support for MCPs: directories under `mcps/` with `mcp.yaml` generate
  `.cursor/mcp.json` (Cursor) and `.mcp.json` (Claude Code)
- Add `mcps/langchain-docs` pointing at https://docs.langchain.com/mcp
- Add the `agents` loadout (extends `base`) carrying the LangChain docs MCP

## 0.3.0

- Add opt-in `superpowers` loadout: vendors obra/superpowers@v6.2.0 skills
  and an adapted SessionStart bootstrap hook (no `extends`; do not combine
  with the Superpowers plugin for the same harness)
- Hard-disable brainstorming visual-companion remote brand/telemetry image
  in the vendored `skills/brainstorming/scripts/server.cjs` (text-only branding)

## 0.2.1

- Require releases on `release/vX.Y.Z` branches; `just release` opens a PR and CI
  annotated-tags the merge commit on `main`/`master`

## 0.2.0

- Add rule to `rules/core/repo-conventions.mdc` to always branch from `main`.
- Align `agents/e2e_test_generator.md` with agent best-practices (charter, JSON I/O, DoD, tools, anti-hacking, blocked@3)
- Align `agents/python_coder.md` with agent best-practices (charter, JSON I/O, DoD, tools, anti-hacking, blocked@3)
- Align `agents/davinci.md` with agent best-practices (charter, JSON I/O, DoD, tools, anti-hacking, blocked@3)
- Add `.claude/skills/skill-security-check`, a loadout-repo-local skill that
  audits a given skill tree via a dedicated subagent for dangerous or nefarious
  behavior (for agents working on this repo; not vendored through loadouts)
- Add `agents/davinci.md`, a code-simplification agent that detects and removes
  common AI-generated code smells, and attach it to the `base` loadout
- Add `agents/e2e_test_generator.md`, a Playwright e2e generator that explores UIs
  via Playwright CLI and MCP and writes missing specs under `/e2e`, attached to
  the `playwright-e2e` loadout
- Point the `playwright-e2e` rule destination and globs at `e2e/` (repo root)
  instead of `tests/e2e/`
- Add loadout support for hooks: directories under `hooks/` sync to `.cursor/hooks/`,
  with generated `.cursor/hooks.json` (Cursor) and `.claude/settings.json` hooks
  (Claude Code) pointing at the same scripts so neither harness sees a duplicate copy
- Add `hooks/deny-dangerous` (pre-tool/shell guard) and attach it to the `base` loadout
- Add loadout support for agents: markdown files under `agents/` sync once to
  `.claude/agents/`, which both Cursor (compatibility path) and Claude Code read
- Add `agents/python_coder.md` and attach it to the `python` loadout
- Add the `typescript` loadout, carrying TypeScript authoring conventions
- Add `rules/typescript/typescript-code-style.mdc`, a simplicity-first TypeScript code style rule

## 0.1.1

- Add the `python` loadout, carrying the language-level Python rules; `python-monorepo` now
  extends it and owns the uv workspace rule
- Add `rules/python/python-code-style.mdc`, a simplicity-first Python code style rule

## 0.1.0

- Initial release: sync, check, update, init, lint, resolve
