# Tasks to resolve

PR: https://github.com/sazlin/loadout/pull/80 (#80)
Phase: verify
Generated: 2026-08-28T12:40:00Z

## TASK-001 [done]

**Title:** Add dedicated test for _wait_until_dead helper
**Severity peak:** important
**Files:** `tests/test_anti_sleep.py`

### Issues (1-3)

#### 1. No newly added tests target _wait_until_dead (`V-001`, important)

- **Source agent:** verifier
- **Location:** `tests/test_anti_sleep.py:94` (`_wait_until_dead`)
- **What's wrong:** PR #80 adds the `_wait_until_dead` polling helper and replaces fixed `time.sleep(0.05)` + `pytest.raises(OSError)` assertions in three existing tests, but does not add any new test functions that explicitly exercise the helper or its timeout/fail behavior. The modified tests are refactors of pre-existing cases and would pass on main with the old sleep-based assertions.
- **Why it matters:** The meaningful-tests verifier requires that newly added tests for newly implemented behavior discriminate base from branch. No dedicated test proves the helper (e.g., timeout path via `pytest.fail`).
- **How to fix:**
  1. Add a new test (or tests) that explicitly target `_wait_until_dead` behavior, such as asserting `pytest.fail` is raised when a live process is still running after the timeout, and/or that the helper returns promptly once `os.kill(pid, 0)` raises `OSError`.
  2. Confirm the new test(s) fail on main (NameError or missing helper) and pass on the PR branch.
  3. Keep existing anti_sleep integration tests as-is; the new unit-style test(s) should cover the helper contract directly.
- **Acceptance criteria:**
  - [ ] At least one newly added test function explicitly targets `_wait_until_dead` (not merely calls it from an existing integration test).
  - [ ] That test fails when checked out on main and passes on the PR branch.
  - [ ] VERIFIERS.md claim 3 evaluates true.
- **Suggested test:** `def test_wait_until_dead_fails_when_process_still_alive(tmp_path):` spawn sleep 60; call `_wait_until_dead(pid, timeout=0.1)`; expect `pytest.fail`. On main without the helper, the test module import or call should fail.

### Verification

```bash
uv run pytest tests/test_anti_sleep.py -q
```

### Out of scope

Do not implement other tasks. Do not refactor unrelated code. Do not edit `VERIFIERS.md`. Do not merge the PR.
