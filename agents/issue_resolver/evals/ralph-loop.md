# Ralph loop: issue_resolver

Goal: this eval must **fail** a blank general-purpose agent and **pass**
`issue_resolver`. Identity checks do not count as differentiation.

Max 5 modify/test iterations.

## Blank protocol

A blank subagent is `generalPurpose` with no `agents/**/*.md`, no `evals.json`,
and no goldens.

Behavior score = `must_find` / `must_not_find` over the whole report blob.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `issue-resolver-tax-after-discount` | FAIL (`_tmp` and `pr merge`) | 0 | Keep. Custom pushes and omits `_tmp` / merge. |

No eval was thrown out.
