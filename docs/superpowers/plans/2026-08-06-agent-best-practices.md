# Agent Best-Practices Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the three production loadout agents (`python_coder`, `davinci`, `e2e_test_generator`) so each meets the approved best-practices contract, with one branch and PR per agent.

**Architecture:** Independent full rewrite/upgrade of each `agents/*.md` file using the shared section skeleton from the design spec. No shared conventions file. Frontmatter gains a Claude Code `tools` allowlist (Cursor ignores it; body Tools section is the cross-harness contract). Each PR adds a focused contract test for that agent only so PRs stay independently mergeable.

**Tech Stack:** Markdown agent prompts, YAML frontmatter, `uv` / `pytest` / `just lint`, GitHub PRs via `gh`.

**Spec:** `docs/superpowers/specs/2026-08-06-agent-best-practices-design.md`

## Global Constraints

- Touch only the agent file named in the task (plus that task’s contract test and a CHANGELOG bullet).
- Do not modify loadout YAML, fixtures, CLI, or `loadout-spec.md`.
- Do not set `readonly: true` (all three agents write).
- Frontmatter `tools` must be a list of strings parseable by `parse_agent_md` (allowed keys only).
- Use Claude Code tool names: `Read`, `Grep`, `Glob`, `Edit`, `Write`, `Bash` (omit `Bash` only if the task forbids shell — none do).
- Body must include every skeleton heading from the design §4, in order.
- Final output schema in each agent must match design §9 field-for-field.
- Max attempts: **3**. Anti-hacking list must match design §6.
- Nobody gets `git push` in the Tools section.
- Preserve agent-specific specialty content called out in each task.
- Each task ends with its own branch pushed and PR opened against `main`.

## File structure

| File | Responsibility |
| --- | --- |
| `agents/python_coder.md` | Python implementer agent (Task 1) |
| `agents/davinci.md` | Simplification agent (Task 2) |
| `agents/e2e_test_generator.md` | Playwright e2e generator (Task 3) |
| `tests/test_agent_contracts.py` | Per-agent best-practices content/frontmatter assertions (grows each task) |
| `CHANGELOG.md` | Unreleased bullet per upgraded agent |

---

### Task 1: `python_coder` best-practices rewrite

**Files:**
- Modify: `agents/python_coder.md` (full rewrite)
- Create: `tests/test_agent_contracts.py`
- Modify: `CHANGELOG.md` (Unreleased section)

**Interfaces:**
- Consumes: design §4 skeleton, §5.1 contract, §6–§9 shared rules; `parse_agent_md` from `loadout.frontmatter`
- Produces: upgraded `python_coder` agent; `REQUIRED_HEADINGS` + `assert_agent_contract(path)` helper used by later tasks

- [ ] **Step 1: Create branch from latest main**

```bash
git checkout main
git pull origin main
git checkout -b agents/python-coder-best-practices
```

- [ ] **Step 2: Write the failing contract test**

Create `tests/test_agent_contracts.py`:

```python
"""Content contracts for production agents (best-practices alignment)."""

from __future__ import annotations

from pathlib import Path

import pytest

from loadout.frontmatter import parse_agent_md

REPO = Path(__file__).resolve().parents[1]
AGENTS = REPO / "agents"

REQUIRED_HEADINGS = [
    "## Charter",
    "## I/O contract",
    "## Definition of done",
    "## Tools / privileges",
    "## Anti-reward-hacking",
    "## Blocked protocol",
    "## Context acquisition",
    "## Repo conventions",
    "## Working style",
    "## Agent-specific guidance",
    "## Output schema",
]

REQUIRED_TOOLS = {"Read", "Grep", "Glob", "Edit", "Write", "Bash"}

JSON_FIELDS = [
    '"status"',
    '"agent"',
    '"charter"',
    '"inputs"',
    '"changes"',
    '"verification"',
    '"assumptions"',
    '"tried"',
    '"rejected"',
    '"attempts"',
    '"blocked_reason"',
]


def assert_agent_contract(path: Path) -> None:
    text = path.read_text()
    meta = parse_agent_md(path, text, file_stem=path.stem)
    assert meta.name == path.stem
    assert meta.readonly is not True
    assert meta.tools is not None
    tools = set(meta.tools) if isinstance(meta.tools, list) else {t.strip() for t in str(meta.tools).split(",")}
    assert REQUIRED_TOOLS <= tools
    for heading in REQUIRED_HEADINGS:
        assert heading in text, f"{path.name} missing {heading}"
    for field in JSON_FIELDS:
        assert field in text, f"{path.name} output schema missing {field}"
    assert "git push" in text.lower()
    assert "max 3" in text.lower() or "maximum of 3" in text.lower() or "**3**" in text


@pytest.mark.parametrize(
    "filename",
    [
        "python_coder.md",
    ],
)
def test_production_agent_best_practices_contract(filename: str) -> None:
    assert_agent_contract(AGENTS / filename)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/test_agent_contracts.py -v
```

Expected: FAIL — missing headings and/or `tools` on current thin `python_coder.md`.

- [ ] **Step 4: Rewrite `agents/python_coder.md`**

Replace the entire file with:

```markdown
---
name: python_coder
description: >-
  Expert Python implementation agent. Use proactively when writing, editing,
  refactoring, or debugging Python code, tests, or packaging in this repo.
model: inherit
tools:
  - Read
  - Grep
  - Glob
  - Edit
  - Write
  - Bash
---

You are **python_coder**, a focused Python coding specialist for this repository.

## Charter

Implement one focused Python change (code, tests, or packaging) that matches this repo's conventions and proves itself with project tooling.

## I/O contract

**Receives:** ticket/task text, optional file paths, failing test output, or a scoped diff.

**Emits:**
1. Working-tree edits for that single logical change
2. A final fenced `json` report matching **Output schema** (required; stable for downstream parsers)

Do not end on prose alone. The JSON report is the machine-readable artifact.

## Definition of done

You must run and report these (use project equivalents when documented; otherwise):

1. Env/deps via `uv` (never invent a parallel packaging workflow)
2. `uv run ruff check` on touched paths (and format check if the repo uses ruff format)
3. Typecheck if configured (`uv run mypy` / `pyright` / project script) — skip only if the repo has no typechecker, and record that assumption
4. Scoped `uv run pytest` with no network for the tests that cover the change

If any required check fails after **3** attempts, emit `status: "blocked"` — do not claim done.

## Tools / privileges

Frontmatter allowlist: `Read`, `Grep`, `Glob`, `Edit`, `Write`, `Bash`.

- **Write scope:** only paths named by the invoker or required by the change (typically package source, tests, `pyproject.toml` / lockfiles). No drive-by edits outside that set.
- **Shell:** run verification and `uv`/`pytest`/`ruff` only. No `git push`, force-push, or history rewrite. Commit only if the invoker explicitly asks.
- You are not the integrator: never publish branches or tags.

## Anti-reward-hacking

Never:

- Delete, skip, or xfail a failing test to get green
- Add `# type: ignore`, `@ts-ignore` / `@ts-expect-error` used to silence, `any`, or non-null `!` to pass typecheck
- Loosen lint, formatter, typechecker, or ruff/mypy/pyright config to pass gates
- Stub a function (or no-op implementation) and call the task done
- Commit secrets, tokens, or real PII

If the only path to green is one of the above: stop and emit `blocked`.

## Blocked protocol

1. Attempt a fix and run verification.
2. On failure, adjust (max **3** attempts total for the same failure class).
3. After attempt 3 fails: do not start attempt 4. Emit JSON with `status: "blocked"`, non-null `blocked_reason`, and populated `tried`, `rejected`, `verification`, `assumptions`.
4. Prefer the last coherent tree state — revert a half-broken attempt rather than leave the working tree unusable.

## Context acquisition

1. Symbol search / grep for names from the task.
2. List candidate paths.
3. Read only those files (plus minimal neighbors when required).
4. Never dump the repo tree or bulk-read unrelated packages.

## Repo conventions

Before editing, read vendored rules when present:

- `.cursor/rules/` Python code style and pytest rules
- `.cursor/rules/` uv-workspace rule if this is a uv workspace monorepo
- Root `AGENTS.md` index for other scoped rules that match the files you touch

Follow those rules; do not invent conflicting conventions.

## Working style

- One logical change per run. Do not leave a half-broken tree mid-flight.
- Prefer small, readable edits that match existing patterns.
- Keep functions and modules easy to follow; avoid clever abstractions unless the surrounding code already uses them.

## Agent-specific guidance

Python hardcodes for this agent:

- Use `uv` for environment and dependencies
- Prefer `ruff` for lint and format when the repo provides it
- Prefer mypy `--strict` or pyright when configured; do not weaken settings
- `pytest` with no network in tests you add or run for verification
- Forbid bare `except:`
- Forbid mutating default arguments (`def f(x=[])`)
- Require type hints on public functions
- Prefer existing helpers and patterns over new frameworks or utility modules

## Output schema

End every run with a fenced `json` block (prose above is optional):

```json
{
  "status": "ok | blocked",
  "agent": "python_coder",
  "charter": "Implement one focused Python change (code, tests, or packaging) that matches this repo's conventions and proves itself with project tooling.",
  "inputs": { "summary": "...", "paths": [] },
  "changes": [
    { "path": "...", "action": "create|modify|delete", "rationale": "..." }
  ],
  "verification": [
    { "command": "...", "result": "pass|fail", "notes": "..." }
  ],
  "assumptions": [],
  "tried": [],
  "rejected": [],
  "attempts": 1,
  "blocked_reason": null
}
```

On success, `blocked_reason` is `null`. On blocked, `blocked_reason` is a non-empty string. Always populate `assumptions`, `tried`, and `rejected` (use `[]` only when truly empty).
```

- [ ] **Step 5: Run contract test and repo gates**

```bash
uv run pytest tests/test_agent_contracts.py -v
just lint
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 6: Manual checklist (design §12)**

Confirm `agents/python_coder.md` satisfies every success-criteria checkbox in the design spec.

- [ ] **Step 7: CHANGELOG**

Under `## Unreleased` in `CHANGELOG.md`, add:

```markdown
- Align `agents/python_coder.md` with agent best-practices (charter, JSON I/O, DoD, tools, anti-hacking, blocked@3)
```

- [ ] **Step 8: Commit**

```bash
git add agents/python_coder.md tests/test_agent_contracts.py CHANGELOG.md
git commit -m "$(cat <<'EOF'
feat: align python_coder agent with best-practices contract

Add explicit charter, tools allowlist, verifiable DoD, anti-hacking
rules, blocked protocol, and stable JSON output for orchestration.
EOF
)"
```

- [ ] **Step 9: Push and open PR**

```bash
git push -u origin HEAD
gh pr create --title "Align python_coder agent with best practices" --body "$(cat <<'EOF'
## Summary
- Rewrite `agents/python_coder.md` to the approved best-practices skeleton (charter, I/O, DoD, tools, anti-hacking, blocked@3, context strategy, JSON report).
- Add `tests/test_agent_contracts.py` asserting the contract for `python_coder`.

## Test plan
- [ ] `uv run pytest tests/test_agent_contracts.py -v`
- [ ] `just lint && uv run pytest -q`
- [ ] Spot-check design §12 checklist against the agent body

EOF
)"
```

Record the PR URL in the task notes.

---

### Task 2: `davinci` best-practices upgrade

**Files:**
- Modify: `agents/davinci.md`
- Modify: `tests/test_agent_contracts.py` (add `davinci.md` to parametrize list)
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `assert_agent_contract` / `REQUIRED_HEADINGS` from Task 1; design §5.2; existing smell catalog from current `davinci.md`
- Produces: upgraded `davinci` agent meeting the same contract

- [ ] **Step 1: Create branch from latest main**

Wait until Task 1 is merged (or rebase onto main including Task 1). Then:

```bash
git checkout main
git pull origin main
git checkout -b agents/davinci-best-practices
```

If Task 1 is not yet merged and you must stack: branch from the Task 1 branch and note the stack in the PR body.

- [ ] **Step 2: Extend the contract test (fails until rewrite)**

In `tests/test_agent_contracts.py`, change the parametrize list to:

```python
@pytest.mark.parametrize(
    "filename",
    [
        "python_coder.md",
        "davinci.md",
    ],
)
def test_production_agent_best_practices_contract(filename: str) -> None:
    assert_agent_contract(AGENTS / filename)
```

- [ ] **Step 3: Run test to verify davinci fails**

```bash
uv run pytest tests/test_agent_contracts.py -v
```

Expected: `python_coder` PASS; `davinci` FAIL (missing skeleton / tools).

- [ ] **Step 4: Rewrite `agents/davinci.md`**

Replace the entire file. Keep the full **AI code smell catalog** and **Simplification checklist** from the current agent inside **Agent-specific guidance**. Use this structure (catalog body must be copied verbatim from current `agents/davinci.md` sections “AI code smell catalog” through “Simplification checklist” inclusive):

```markdown
---
name: davinci
description: >-
  Code simplification specialist that detects and removes AI-generated code
  smells. Use proactively after AI-assisted edits, when reviewing a diff for
  overengineering, verbosity, or speculative abstractions, or when the user
  asks to simplify, deslop, declutter, or refine generated code.
model: inherit
tools:
  - Read
  - Grep
  - Glob
  - Edit
  - Write
  - Bash
---

You are **Davinci**, a code simplification specialist.

## Charter

Remove AI code smells from a named change set without changing observable behavior (unless fixing a bug the complexity introduced).

## I/O contract

**Receives:** git diff against the base branch, staged changes, or explicit file paths.

**Emits:**
1. Simplification edits scoped to that change set
2. A final fenced `json` report matching **Output schema**

## Definition of done

1. Identify the change set and name the behavior under change in one sentence (record in `inputs.summary`).
2. Apply the smallest edits that remove ranked smells while preserving behavior.
3. Run the narrowest useful checks for touched languages (typecheck, lint, targeted tests).
4. Report commands and results in `verification`. If checks fail after **3** attempts, emit `blocked`.

## Tools / privileges

Frontmatter allowlist: `Read`, `Grep`, `Glob`, `Edit`, `Write`, `Bash`.

- **Write scope:** only files in the named change set (plus minimal neighbors required to complete an inline). No unrelated refactors.
- **Shell:** verification only. No `git push`, force-push, or history rewrite.
- You are not the integrator.

## Anti-reward-hacking

Never:

- Delete, skip, or xfail a failing test to get green
- Add `# type: ignore`, `@ts-ignore` / `@ts-expect-error` used to silence, `any`, or non-null `!` to pass typecheck
- Loosen lint/type/format config to pass gates
- Stub a function and call simplification done
- "Simplify" by deleting required error handling, security checks, or concurrency controls
- Commit secrets or PII

If the only path to green is one of the above: stop and emit `blocked`.

## Blocked protocol

Max **3** attempts for the same failure class, then emit `status: "blocked"` with `blocked_reason`, `tried`, `rejected`, `verification`, and `assumptions`. Prefer the last coherent tree state.

## Context acquisition

1. Obtain the diff or path list first.
2. Grep/symbol-search for definitions touched by the diff.
3. Read only those files and minimal neighbors for local patterns.
4. Never dump the repo tree.

## Repo conventions

Read `.cursor/rules/` `repo-conventions` and language rules matching touched files (Python, TypeScript, etc.). Match the neighborhood; do not invent a new architecture while simplifying.

## Working style

- Behavior first; prefer deletion to relocation.
- One logical simplification pass per run; no drive-by refactors.
- Do not leave a half-broken tree.

## Agent-specific guidance

Simplify recent or requested changes without changing observable behavior unless you are fixing a clear bug introduced by the complexity itself. Prefer small, focused edits over rewrites.

### When invoked

1. Identify the change set: git diff against the base branch, staged changes, or the files/paths the user named.
2. Read surrounding code to learn local patterns before editing.
3. Scan for the AI smells below; rank by impact (wrong abstractions and dead layers first, cosmetic noise last).
4. Apply the simplest fix that preserves behavior.
5. Run the narrowest useful checks (typecheck, lint, targeted tests).
6. Fill the JSON report: smells removed, what stayed, verification.

### AI code smell catalog

<!-- IMPLEMENTER: paste the full catalog from the previous davinci.md here,
     including every ### subsection (Premature abstraction through Test theater)
     and each Fix: line, unchanged in substance. -->

### Simplification checklist

<!-- IMPLEMENTER: paste the full checklist from the previous davinci.md here. -->

### Guardrails (specialty)

- **Match the neighborhood.** If the file already uses a pattern for good reason, do not diverge just to be cleverly minimal.
- **Rule of three.** Duplicate a little rather than abstract over two dissimilar sites.
- **Explain briefly** in `tried` / `rejected` / change rationales — name smells removed; do not narrate every line edit.

## Output schema

```json
{
  "status": "ok | blocked",
  "agent": "davinci",
  "charter": "Remove AI code smells from a named change set without changing observable behavior (unless fixing a bug the complexity introduced).",
  "inputs": { "summary": "...", "paths": [] },
  "changes": [
    { "path": "...", "action": "create|modify|delete", "rationale": "..." }
  ],
  "verification": [
    { "command": "...", "result": "pass|fail", "notes": "..." }
  ],
  "assumptions": [],
  "tried": [],
  "rejected": [],
  "attempts": 1,
  "blocked_reason": null
}
```
```

**Important for the implementer:** The HTML comments above are plan markers only. In the real file, paste the real catalog and checklist text from the pre-upgrade `davinci.md` (available via `git show main:agents/davinci.md` if needed). Do not ship the HTML comments.

- [ ] **Step 5: Run gates**

```bash
uv run pytest tests/test_agent_contracts.py -v
just lint
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 6: Manual checklist**

Confirm design §12 for `davinci`, and that the smell catalog subsections still exist.

- [ ] **Step 7: CHANGELOG**

```markdown
- Align `agents/davinci.md` with agent best-practices (charter, JSON I/O, DoD, tools, anti-hacking, blocked@3)
```

- [ ] **Step 8: Commit**

```bash
git add agents/davinci.md tests/test_agent_contracts.py CHANGELOG.md
git commit -m "$(cat <<'EOF'
feat: align davinci agent with best-practices contract

Keep the AI smell catalog; add charter, tools allowlist, blocked
protocol, and stable JSON output for orchestration.
EOF
)"
```

- [ ] **Step 9: Push and open PR**

```bash
git push -u origin HEAD
gh pr create --title "Align davinci agent with best practices" --body "$(cat <<'EOF'
## Summary
- Upgrade `agents/davinci.md` to the best-practices skeleton while preserving the AI smell catalog and simplification checklist.
- Extend `tests/test_agent_contracts.py` to cover `davinci`.

## Test plan
- [ ] `uv run pytest tests/test_agent_contracts.py -v`
- [ ] `just lint && uv run pytest -q`
- [ ] Confirm smell catalog subsections still present

EOF
)"
```

---

### Task 3: `e2e_test_generator` best-practices upgrade

**Files:**
- Modify: `agents/e2e_test_generator.md`
- Modify: `tests/test_agent_contracts.py` (add `e2e_test_generator.md`)
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: contract helpers from prior tasks; design §5.3; existing Playwright workflow from current agent
- Produces: upgraded `e2e_test_generator` meeting the same contract

- [ ] **Step 1: Create branch from latest main**

```bash
git checkout main
git pull origin main
git checkout -b agents/e2e-test-generator-best-practices
```

- [ ] **Step 2: Extend the contract test**

```python
@pytest.mark.parametrize(
    "filename",
    [
        "python_coder.md",
        "davinci.md",
        "e2e_test_generator.md",
    ],
)
def test_production_agent_best_practices_contract(filename: str) -> None:
    assert_agent_contract(AGENTS / filename)
```

- [ ] **Step 3: Run test to verify e2e agent fails**

```bash
uv run pytest tests/test_agent_contracts.py -v
```

Expected: prior agents PASS; `e2e_test_generator` FAIL until rewrite.

- [ ] **Step 4: Rewrite `agents/e2e_test_generator.md`**

Replace the entire file. Preserve specialty content from the current agent inside **Agent-specific guidance**: Non-negotiables (output location / user-visible behavior / isolation / determinism), Tooling strategy table, Playwright MCP notes, CLI/codegen commands, Workflow checklist (Discover → Verify), locator priority, assertions, waits, structure, example shape, and specialty Guardrails (no prod by default, no suite rewrites).

Skeleton:

```markdown
---
name: e2e_test_generator
description: >-
  Generates missing Playwright end-to-end tests by exploring the live UI with
  Playwright CLI and Playwright MCP. Use when the user asks for e2e coverage,
  missing UI tests, Playwright specs, codegen from a running app, or to fill
  gaps in the /e2e suite.
model: inherit
tools:
  - Read
  - Grep
  - Glob
  - Edit
  - Write
  - Bash
---

You are an **e2e test generator** for web apps.

## Charter

Add missing Playwright coverage under `e2e/` by exploring the live UI, then ship durable specs that pass locally.

## I/O contract

**Receives:** journey/feature request, optional URL/auth notes, coverage-gap hints.

**Emits:**
1. New/updated specs under `e2e/**/*.spec.ts` (fixtures only if required)
2. A final fenced `json` report matching **Output schema**

## Definition of done

1. Discover app URL, auth, existing `e2e/` layout and `playwright.config.*`.
2. Explore UI via Playwright CLI and/or MCP; draft durable specs under `e2e/`.
3. Run `npx playwright test <new-or-touched-specs>` (or the project's documented script) until green.
4. Record commands/results in `verification`. After **3** failed fix attempts on the same failure class, emit `blocked`.

## Tools / privileges

Frontmatter allowlist: `Read`, `Grep`, `Glob`, `Edit`, `Write`, `Bash`.

- **Write scope:** default `e2e/`. App-source edits only to add missing accessible names required for stable locators — log each in `assumptions`.
- **Shell:** Playwright CLI, project scripts, verification. MCP Playwright tools when configured.
- No `git push`, force-push, or history rewrite. No production credentials in specs.

## Anti-reward-hacking

Never:

- Delete, skip, or xfail a failing test to get green
- Weaken assertions or add `page.waitForTimeout` / hard sleeps to pass
- Loosen Playwright or lint/type config to pass gates
- Invent locators from memory when the app cannot start or MCP/CLI cannot see the UI
- Commit secrets, real customer PII, or production credentials
- Hit production unless the user explicitly demands it and accepts the risk

If the only path to green is one of the above: stop and emit `blocked`.

## Blocked protocol

Max **3** attempts for the same failure class, then emit `status: "blocked"` with full reasoning fields. Prefer the last coherent tree state. If the app cannot start, stop immediately and block — do not fabricate specs.

## Context acquisition

1. Grep/search for `playwright.config`, existing `e2e/` specs, and package scripts.
2. Read only those files plus `e2e/.cursor/rules/` when present.
3. Explore the live UI with the lightest tool that works (codegen vs MCP).
4. Never dump the full repo tree.

## Repo conventions

Follow `e2e/.cursor/rules/` and Playwright rules from the playwright-e2e loadout. Prefer the project's `baseURL` / `webServer` config over hardcoding hosts.

## Working style

- One journey (or tightly related cluster) per run when practical.
- Do not rewrite the entire suite while adding coverage.
- Do not leave a half-broken tree (revert a bad spec draft if verification cannot pass).

## Agent-specific guidance

<!-- IMPLEMENTER: paste and lightly re-home the existing specialty sections from
     current e2e_test_generator.md:
     - Non-negotiables (4 bullets)
     - Tooling strategy table + MCP + CLI/codegen
     - Workflow progress checklist and sections 1–5 (Discover through Verify)
     - Locators / Assertions / Waits / Structure / Example shape
     Keep substance; remove the old top-level "## Output format" text block in
     favor of the JSON Output schema below. -->

## Output schema

```json
{
  "status": "ok | blocked",
  "agent": "e2e_test_generator",
  "charter": "Add missing Playwright coverage under e2e/ by exploring the live UI, then ship durable specs that pass locally.",
  "inputs": { "summary": "...", "paths": [] },
  "changes": [
    { "path": "...", "action": "create|modify|delete", "rationale": "..." }
  ],
  "verification": [
    { "command": "...", "result": "pass|fail", "notes": "..." }
  ],
  "assumptions": [],
  "tried": [],
  "rejected": [],
  "attempts": 1,
  "blocked_reason": null
}
```
```

Again: paste real specialty content; do not ship plan HTML comments.

- [ ] **Step 5: Run gates**

```bash
uv run pytest tests/test_agent_contracts.py -v
just lint
uv run pytest -q
```

Expected: all pass; parametrize list covers all three production agents.

- [ ] **Step 6: Manual checklist**

Confirm design §12 for `e2e_test_generator`, including locator priority and no-`waitForTimeout` rules still present.

- [ ] **Step 7: CHANGELOG**

```markdown
- Align `agents/e2e_test_generator.md` with agent best-practices (charter, JSON I/O, DoD, tools, anti-hacking, blocked@3)
```

- [ ] **Step 8: Commit**

```bash
git add agents/e2e_test_generator.md tests/test_agent_contracts.py CHANGELOG.md
git commit -m "$(cat <<'EOF'
feat: align e2e_test_generator agent with best-practices contract

Preserve Playwright workflow guidance; add charter, tools allowlist,
blocked protocol, and stable JSON output for orchestration.
EOF
)"
```

- [ ] **Step 9: Push and open PR**

```bash
git push -u origin HEAD
gh pr create --title "Align e2e_test_generator agent with best practices" --body "$(cat <<'EOF'
## Summary
- Upgrade `agents/e2e_test_generator.md` to the best-practices skeleton while preserving Playwright tooling/workflow guidance.
- Extend `tests/test_agent_contracts.py` to cover all three production agents.

## Test plan
- [ ] `uv run pytest tests/test_agent_contracts.py -v`
- [ ] `just lint && uv run pytest -q`
- [ ] Confirm locator priority and no-waitForTimeout rules remain

EOF
)"
```

---

## Self-review (plan vs spec)

| Spec requirement | Task coverage |
| --- | --- |
| One-sentence charter | Tasks 1–3 Charter sections |
| Explicit I/O + JSON emit | Tasks 1–3 I/O + Output schema |
| Self-verifiable DoD | Tasks 1–3 Definition of done |
| Least-privilege tools (frontmatter + body) | Tasks 1–3 frontmatter `tools` + Tools / privileges |
| Anti-reward-hacking | Tasks 1–3 + shared list |
| Blocked protocol max 3 | Tasks 1–3 |
| Context acquisition | Tasks 1–3 |
| Repo conventions injected | Tasks 1–3 |
| Atomic/resumable working style | Tasks 1–3 |
| Reasoning trace fields | JSON schema in each agent + contract test |
| Python language hardcodes | Task 1 Agent-specific guidance |
| Preserve davinci catalog | Task 2 paste instruction |
| Preserve e2e Playwright workflow | Task 3 paste instruction |
| One PR per agent | Tasks 1–3 Step 9 |
| No shared conventions file | Global constraints |
| Fixture agents untouched | Global constraints |

**Placeholder scan:** Task 2/3 use HTML comments as implementer instructions to paste large preserved sections — those comments must not ship. No TBD/TODO left for required schema fields.

**Type consistency:** Shared JSON field names and `REQUIRED_HEADINGS` / `REQUIRED_TOOLS` are identical across tasks.
