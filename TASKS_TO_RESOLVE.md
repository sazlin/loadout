# Tasks to resolve

PR: https://github.com/sazlin/loadout/pull/78 (#78)
Phase: panel
Generated: 2026-08-27T12:16:00Z

## TASK-001 [done]

**Title:** Align PROMPT_BUILD comments with --arg pr_head_ref and document \\u0027 escape
**Severity peak:** important
**Files:** `.github/workflows/pr-review-harness.yml`

### Issues (1-3)

#### 1. PROMPT_BUILD comment contradicts new --arg pr_head_ref wiring (`M-001`, important)

- **Source agent:** review_maintainability
- **Location:** `.github/workflows/pr-review-harness.yml:191` (`PROMPT_BUILD`)
- **What's wrong:** The PROMPT_BUILD block comment still says branch binding and envVars "read env.PR_HEAD_REF via jq only", and that PR_HEAD_REF "must never expand inside bash double quotes". The implementation passes `--arg pr_head_ref "${PR_HEAD_REF}"` in both jq calls (lines 208 and 224), but the comment was not updated.
- **Why it matters:** A future editor following the comment may revert to `env.PR_HEAD_REF` in jq or remove the `--arg` lines, reintroducing confusion and making the workflow harder to change safely.
- **How to fix:**
  1. Replace the three-line PROMPT_BUILD comment (lines 189-191) with wording that matches the implementation.
  2. Explain that PR_HEAD_REF is passed to jq only via `--arg pr_head_ref "${PR_HEAD_REF}"`; the value is not re-parsed for shell metacharacters when expanded from an environment variable inside double quotes.
  3. Clarify that `"${PR_HEAD_REF}"` is allowed only as the --arg value, not embedded inside the jq program string.
  4. Mention both jq invocations (prompt build and dispatch body) use the same --arg pattern.
- **Acceptance criteria:**
  - [ ] The PROMPT_BUILD comment no longer references `env.PR_HEAD_REF` or jq `env` binding.
  - [ ] The comment accurately describes the --arg pr_head_ref pattern used on lines 208 and 224.
  - [ ] Reading the comment alongside the code does not imply `"${PR_HEAD_REF}"` is forbidden.
- **Suggested test:** none

#### 2. Non-obvious \\u0027 apostrophe escape lacks an explaining comment (`M-002`, important)

- **Source agent:** review_maintainability
- **Location:** `.github/workflows/pr-review-harness.yml:213` (`PROMPT_BUILD jq filter`)
- **What's wrong:** The PR replaces literal `'` characters around `$pr_head_ref` in the jq filter with `\\u0027`, but there is no comment explaining that this is required because the jq program is wrapped in a bash single-quoted string where a literal apostrophe would terminate the string.
- **Why it matters:** Without context, a maintainer may "simplify" `\\u0027` back to `'` for readability, breaking bash parsing of the workflow step.
- **How to fix:**
  1. Add a short inline comment above the branch-binding lines (near line 213), e.g. "# \\u0027 = apostrophe: literal ' breaks the bash-single-quoted jq filter below".
  2. Extend `test_pr_review_harness_workflow_smoke_dispatch_configuration` to assert `\\u0027` is present in the dispatch script block and that bare `not '" + $pr_head_ref` is absent.
- **Acceptance criteria:**
  - [ ] A reader can see in-file why `\\u0027` is used instead of `'` without reading the PR diff.
  - [ ] `test_pr_review_harness_workflow_smoke_dispatch_configuration` asserts `\\u0027` in `_dispatch_step_script()`.
- **Suggested test:** Extend test_pr_review_harness_workflow_smoke_dispatch_configuration

### Verification

```bash
uv run pytest tests/test_pr_review_dogfood.py -q
```

### Out of scope

Do not implement other tasks. Do not refactor unrelated code. Do not edit `VERIFIERS.md`. Do not merge the PR. Do not revert `--arg pr_head_ref` to `env.PR_HEAD_REF as $pr_head_ref` (C-001 was assessed false positive).
