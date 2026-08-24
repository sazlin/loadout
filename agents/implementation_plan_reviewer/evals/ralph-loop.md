# Ralph loop: implementation_plan_reviewer

Goal: this eval must **fail** a blank general-purpose agent and **pass**
the named custom agent. Identity checks do not count as differentiation.

Max 5 modify/test iterations. Throw the eval out if it still cannot
separate blank vs custom.

## Blank protocol

A blank subagent is `generalPurpose` with no agent markdown. Behavior score
= `must_find` / `must_not_find` over the whole report blob.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `implementation-plan-reviewer-missing-tests` | FAIL (filed `_tmp`, missed exponential tests) | 0 | Keep. Custom reports missing tests and exponential backoff, omits `_tmp`. |

No eval was thrown out.
