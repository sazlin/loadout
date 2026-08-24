# Ralph loop: implementation_build_reviewer

Goal: this eval must **fail** a blank general-purpose agent and **pass**
the named custom agent. Identity checks do not count as differentiation.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `implementation-build-reviewer-linear-delay` | FAIL (filed `_tmp`, missed linear vs exponential) | 0 | Keep. Custom reports linear vs exponential and omits `_tmp`. |

No eval was thrown out.
