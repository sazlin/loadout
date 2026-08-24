# Ralph loop: implementation_orchestrator

Goal: this eval must **fail** a blank general-purpose agent and **pass**
the named custom agent. Identity checks do not count as differentiation.

## Results

| Eval | Blank iter 0 | Ralph iters | Outcome |
| --- | --- | --- | --- |
| `implementation-orchestrator-prd-loop` | FAIL (in-process `def export_widgets`, no skill names / 10 cap) | 0 | Keep. Custom names the four skills and the 10-loop cap, omits in-process implementation. |

No eval was thrown out.
