# Ralph loop: verifier

Goal: this eval must **fail** a blank general-purpose agent and **pass**
`verifier`. Identity checks do not count as differentiation.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `verifier-debugger-claim-false` | FAIL (`eval()` false positive, skipped any) | 0 | Keep. Custom files a false debugger claim across three ordered claims. |

No eval was thrown out.
