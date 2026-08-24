# Ralph loop: implementation_builder

Goal: this eval must **fail** a blank general-purpose agent and **pass**
the named custom agent. Identity checks do not count as differentiation.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `implementation-builder-exponential-backoff` | FAIL (hit `_tmp`, no exponential backoff) | 0 | Keep. Custom implements exponential backoff and omits the bait. |

No eval was thrown out.
