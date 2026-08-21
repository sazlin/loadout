# Ralph loop: playwright_generator

Goal: this eval must **fail** a blank general-purpose agent and **pass**
the named custom agent. Identity checks do not count as differentiation.

Max 5 modify/test iterations.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `playwright-generator-add-todo` | FAIL on `processdata`; also missed `spec:` + `getbyrole` | 1 | Keep. Golden custom passes full score. |

No eval was thrown out.
