# Ralph loop: verifier

Goal: this eval must **fail** a blank general-purpose agent and **pass**
`verifier`. Identity checks do not count as differentiation.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `verifier-any-claim-false` | FAIL (`eval()` false positive, skipped any) | 0 | Keep. Custom files TypeScript any only. |

No eval was thrown out.
