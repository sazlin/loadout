# Tasks to resolve

PR: example/repo#1
Phase: panel
Generated: 2026-08-18T00:00:00Z

## TASK-001 [open]

**Title:** Apply tax after discount in discounted_total
**Severity peak:** important
**Files:** `pricing.py`

### Issues (1-3)

#### 1. Tax added as a flat amount (`C-001`, important)

- **Source agent:** review_correctness
- **Location:** `pricing.py:9` (`discounted_total`)
- **What's wrong:** `return price - discount + tax_rate` adds tax_rate as a constant, not a rate.
- **Why it matters:** Amounts due are wrong.
- **How to fix:**
  1. Return `(price - discount) * (1 + tax_rate)`.
- **Acceptance criteria:**
  - [ ] discounted_total(100, 10, 0.1) is 99
- **Suggested test:** assert tax applies after discount

### Out of scope

Do not remove `_tmp`. Do not merge the PR. Do not edit VERIFIERS.md.
