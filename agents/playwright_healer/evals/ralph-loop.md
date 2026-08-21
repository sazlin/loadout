# Ralph loop: playwright_healer

Goal: this eval must **fail** a blank general-purpose agent and **pass**
the named custom agent. Identity checks do not count as differentiation.

Max 5 modify/test iterations.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `playwright-healer-locator-drift` | FAIL on `test.fixme`; also missed `getbyrole` | 1 | Keep. Golden custom passes full score. |

No eval was thrown out.
