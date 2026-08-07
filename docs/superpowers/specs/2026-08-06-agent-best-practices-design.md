# Design: Agent best-practices alignment

Status: approved for planning  
Date: 2026-08-06  
Audience: implementing engineer or coding agent

---

## 1. Problem

Loadout ships three production subagents (`python_coder`, `davinci`, `e2e_test_generator`). They vary widely in prompt quality. Orchestrated use needs non-negotiable contracts: one-sentence charter, stable machine-readable I/O, self-verifiable definition of done, least-privilege tools, anti-reward-hacking rules, blocked protocol with an iteration budget, and a context-acquisition strategy. Today only parts of that exist (strongest in `e2e_test_generator` and `davinci`; weakest in `python_coder`).

## 2. Scope

**In scope**

- `agents/python_coder.md` (python loadout)
- `agents/davinci.md` (base loadout)
- `agents/e2e_test_generator.md` (playwright-e2e loadout)

**Out of scope**

- Fixture agents under `tests/fixtures/`
- New agents (TypeScript implementer, pure reviewer, integrator)
- Shared conventions file or include mechanism
- Loadout YAML wiring changes (agents already selected)
- CLI / sync / `loadout-spec.md` changes unless validation unexpectedly rejects allowed frontmatter

## 3. Decisions (from design review)

| Topic | Choice |
| --- | --- |
| Agent set | Production three only |
| Tool privilege encoding | Frontmatter (`tools`, and `readonly` only if read-only) **plus** matching Tools section in the body |
| Structure sharing | Same section skeleton inlined in each agent; no shared file |
| Output contract | Final artifact is a stable JSON object in a fenced `json` block; prose above is optional |
| Iteration budget | Max 3 attempts, then `status: "blocked"` |
| Delivery approach | Independent full rewrite/upgrade per agent (Approach 1) |
| PR shape | One dedicated branch + PR per agent |

## 4. Shared skeleton

Every agent body uses these headings, in order:

1. **Charter** — exactly one sentence
2. **I/O contract** — what it receives; what it must emit
3. **Definition of done** — commands the agent runs to prove success
4. **Tools / privileges** — mirrors frontmatter; path scope; forbids `git push` and history rewrite
5. **Anti-reward-hacking** — blunt forbid list (see §6)
6. **Blocked protocol** — max 3 attempts; structured failure
7. **Context acquisition** — grep/symbol search first; read only named files; never dump the tree
8. **Repo conventions** — paths to vendored rules for that loadout
9. **Working style** — one logical change per run; do not leave a half-broken tree
10. **Agent-specific guidance** — specialty content (smell catalog, Playwright workflow, Python hardcodes)
11. **Output schema** — required final JSON report

Frontmatter keeps `name`, `description`, `model: inherit`. Add `tools` appropriate to the role. None of the three agents is a pure reviewer, so none sets `readonly: true`. Path allowlists are expressed in the body (no harness key for path scope).

## 5. Per-agent contracts

### 5.1 `python_coder`

- **Charter:** Implement one focused Python change (code, tests, or packaging) that matches this repo’s conventions and proves itself with project tooling.
- **Receives:** ticket/task text, optional file paths, failing test output, or a scoped diff.
- **Emits:** working-tree edits + final JSON report.
- **Tools:** read/search + edit/write + shell. Body forbids `git push`, force-push, history rewrite, and relaxing lint/type config.
- **Path scope:** only paths named by the invoker or required by the change (typically package source, tests, packaging manifests). No drive-by edits outside that set.
- **DoD:** use `uv` for env/deps; `ruff check` and format check (or project equivalent); typecheck if mypy/pyright is configured; scoped `pytest` with no network. Report exact commands and results.
- **Language hardcodes:** forbid bare `except:`; forbid mutating default args; require type hints on public functions; prefer existing patterns over new frameworks.

### 5.2 `davinci`

- **Charter:** Remove AI code smells from a named change set without changing observable behavior (unless fixing a bug the complexity introduced).
- **Receives:** base-branch diff, staged diff, or explicit paths.
- **Emits:** simplification edits + final JSON report.
- **Tools:** read/search + edit/write + shell; writes scoped to the change set. No `git push`.
- **DoD:** narrowest useful typecheck/lint/tests for touched languages; preserved behavior named in the report.
- **Preserve:** existing AI smell catalog and simplification checklist as agent-specific guidance.

### 5.3 `e2e_test_generator`

- **Charter:** Add missing Playwright coverage under `e2e/` by exploring the live UI, then ship durable specs that pass locally.
- **Receives:** journey/feature request, optional URL/auth notes, coverage-gap hints.
- **Emits:** new/updated `e2e/**/*.spec.ts` (fixtures only if required) + final JSON report.
- **Tools:** read/search + edit/write + shell; body allows Playwright CLI/MCP. Default write scope `e2e/`. App-source edits only for missing accessible names needed for stable locators, called out in `assumptions`.
- **DoD:** project Playwright test command on new/touched specs green; no `waitForTimeout`; no weakened assertions to pass.
- **Preserve:** tooling strategy table, locator priority, QA prioritization, and workflow checklist as agent-specific guidance.

## 6. Anti-reward-hacking

Stated bluntly in every agent. Never:

- Delete, skip, or xfail a failing test to get green
- Add `# type: ignore`, `@ts-ignore` / `@ts-expect-error` used to silence, `any`, or non-null `!` assertions to pass typecheck
- Loosen lint, formatter, typechecker, or tsconfig/ruff/biome config to pass gates
- Stub a function (or no-op implementation) and call the task done
- Weaken assertions or add hard sleeps / `waitForTimeout` to pass e2e
- Commit secrets, real PII, or production credentials

If the only path to green is one of the above: stop and emit `blocked`.

## 7. Blocked protocol

1. Attempt a fix and run verification.
2. On failure, adjust once per remaining attempt (max **3** attempts total for the same failure class).
3. After attempt 3 fails: do not start attempt 4. Emit JSON with `status: "blocked"`, non-null `blocked_reason`, and populated `tried`, `rejected`, `verification`, `assumptions`.
4. Prefer leaving the tree in the last coherent state (revert a half-broken attempt rather than ship a broken intermediate).

## 8. Context acquisition and conventions

1. Symbol search / grep for names from the task.
2. List candidate paths.
3. Read only those files (plus minimal neighbors when required).
4. Never dump the repo tree or bulk-read unrelated packages.
5. Read vendored rules before editing:
   - `python_coder` → `.cursor/rules/` Python style + pytest (+ uv-workspace if present)
   - `davinci` → repo-conventions + language rules for touched files
   - `e2e_test_generator` → `e2e/.cursor/rules/` and Playwright conventions

Ambiguity is logged in JSON `assumptions`, not silently resolved. `tried` and `rejected` are required on both `ok` and `blocked`.

## 9. Output schema

Required final message artifact (fenced `json`):

```json
{
  "status": "ok | blocked",
  "agent": "<name>",
  "charter": "<one sentence>",
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

On success, `blocked_reason` is `null`. On blocked, `blocked_reason` is a non-empty string.

## 10. Frontmatter `tools` guidance

Use the Cursor/Claude shared subset already allowed by loadout-spec §5.10. Exact tool identifier strings must match what the harness documents at implementation time (read current Cursor/Claude agent docs when writing each PR). Intent per agent:

| Agent | Capability intent |
| --- | --- |
| `python_coder` | Read, search, edit/write, shell |
| `davinci` | Read, search, edit/write, shell |
| `e2e_test_generator` | Read, search, edit/write, shell (Playwright CLI/MCP via shell/MCP config) |

Body Tools section restates the same privileges and adds path scope + git push ban. Nobody gets git push except a future integrator agent (not in this work).

## 11. Delivery

| Order | Branch | File | Notes |
| --- | --- | --- | --- |
| 1 | `agents/python-coder-best-practices` | `agents/python_coder.md` | Full rewrite; largest gap |
| 2 | `agents/davinci-best-practices` | `agents/davinci.md` | Upgrade; keep smell catalog |
| 3 | `agents/e2e-test-generator-best-practices` | `agents/e2e_test_generator.md` | Upgrade; keep Playwright workflow |

Each PR lands on `main` (or stacks only if review prefers). No loadout YAML changes. Verification: existing repo lint/tests that cover agent frontmatter; human review that each best-practice checkbox in §12 is satisfied.

## 12. Success criteria

For each agent, a reviewer can answer **yes** to:

- [ ] One-sentence charter
- [ ] Explicit I/O contract with stable JSON emit
- [ ] Self-verifiable definition of done
- [ ] Least-privilege tools in frontmatter and body
- [ ] Anti-reward-hacking rules stated bluntly
- [ ] Blocked protocol with max 3 attempts
- [ ] Context acquisition strategy
- [ ] Repo conventions injected by path
- [ ] Atomic/resumable working style
- [ ] Reasoning trace fields (`tried`, `rejected`, `assumptions`) in the output schema
- [ ] Language-specific hardcodes where applicable (Python / Playwright)

## 13. Risks

- **Tool identifier drift:** harness tool names may differ between Cursor and Claude Code. Mitigation: use the documented shared subset; if a name is rejected by lint, adjust within allowed keys without widening privileges.
- **Path allowlists are soft:** body text is not OS-enforced. Acceptable for this pass; real enforcement would need harness support.
- **Duplicated skeleton:** three copies of section headings will drift over time. Accepted intentionally (no shared file).
