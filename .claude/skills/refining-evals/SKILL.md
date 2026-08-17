---
name: refining-evals
description: >-
  Use when refining agent evals in the loadout repo, differentiating a custom
  reviewer from a blank generalPurpose reviewer, or running a Ralph loop on
  evals; when an eval a blank agent also passes, a fail is keyword-lucky
  (synonym miss), or must_not_find is too specific (rare exact phrases a
  blank never uttered).
---

# Refining evals

Prove an eval **fails a blank general-purpose reviewer** and **passes the
named custom agent** on behavior. Identity checks are not differentiation.

Vendored on the `agents` loadout. Use when proving a specialist eval
fails a blank general-purpose reviewer and still passes the named custom agent.

## Overview

A competent blank agent finds obvious planted bugs. The eval is only real
if the **custom agent stays in dimension** and the **blank files the
out-of-scope bait**. Keyword luck and `"agent": "review_*"` mismatches
are fake splits.

**Core principle:** the differentiator is stay-in-dimension / protocol,
not "did you notice the obvious bug."

```
NO KEEP WITHOUT: blank fails score_behavior AND live custom passes
full score. Identity fails do not count.
```

**Violating the letter is violating the spirit.**

## When to use

- Writing or tightening agent evals (`agents/<name>/evals/`)
- A blank `generalPurpose` subagent also **passes** `score_behavior`
- A blank **fails** only by synonym miss (`PascalCase` vs `camel`,
  `release` vs `drain`)
- `must_not_find` is a conjunction of rare review-speak a blank never said
- Need a Ralph loop (inspect blank filing → retune one eval → re-score)

## When not to use

- Schema-only checks of a custom agent (use the full scorer; no blank)
- Agent-prose edits with no fixture or `evals.json` change
- Ordinary unit tests that do not claim specialist differentiation

## Protocol

**Custom / specialist (or golden):** named agent, follows `agents/<name>/<name>.md`,
gets the fixture. Must **pass** the full scorer.

**Blank:** `generalPurpose` only. Same fixture. Generic JSON schema so
output is scoreable. Blank must not read `agents/<name>/<name>.md`. **Neither**
blank nor custom eval subject may read `evals.json`, `goldens/`,
`blank_runs/`, or `ralph-loop.md`. The custom agent **does** read its
own `agents/<name>/<name>.md`.

Run **all** blanks in parallel for the first baseline. Ralph **one eval
per loop** after that — do not retune every spec from one blank's wording.

### Blank prompt shape

```text
You are a general-purpose code reviewer. Review only:
<FIXTURE_PATH>

Do not read agents/, agents/<name>/evals/evals.json, goldens/,
blank_runs/, or ralph-loop.md.

Return JSON with an "issues" array. Each issue: id, title, severity,
file, line, symbol, whats_wrong, why_it_matters, how_to_fix,
acceptance_criteria, suggested_test, do_not_change.
```

Save the raw fenced JSON **verbatim**. Never paraphrase, condense, or
"clean up" wording before scoring (that can insert specialist tokens
and corrupt the transcript).

## Scoring

`tests/review_eval_score.py`. Keywords are **lowercased substrings**.
Each `must_find` / `must_not_find` item is **AND** inside one issue
blob, **OR** across issues.

| Function | What it checks | Use on |
| --- | --- | --- |
| `score_behavior` | `must_find` / `must_not_find` or `expected_groups` / `expected_dropped` | blank vs custom |
| `score_dimension_report` | schema + `agent` identity + behavior | custom / golden only |
| `score_orchestrator_report` | orchestrator schema + identity + groups | custom / golden only |

Score **both ways** every time: full schema for custom; behavior-only
for blank vs custom. A blank that fails only because
`"agent" != "review_correctness"` has not been differentiated.

**`must_find`:** words that appear in the fixture defect (e.g. `pop`,
`qty`, `timeout`). Not the specialist's pet phrasing.

**`must_not_find`:** one token the blank is likely to say — a symbol
(`_tmp`, `processdata`, `processurls`) or a dimension leak (`sql`,
`ssrf`). Not an AND of rare phrases (`rename _tmp` AND `poor comment`).

## Design the fixture first

1. Plant the in-dimension defects the specialist must report.
2. Plant **one loud out-of-scope bait** before the first blank run
   (unused `_tmp` in a correctness file, SQL in a maintainability file,
   unused `processUrls` / SSRF-shaped helper in a scale file,
   unused `processData` in a security file).
3. Write the spec (`must_find` / `must_not_find` or `expected_groups`).
4. Confirm the custom agent (or golden) **passes**.
5. Run the blank. If it **passes**, or **fails only by keyword luck**,
   the eval does not verify specialist behavior — enter the Ralph loop.

Obvious bugs are found by any competent agent. The bait is the split.

## Ralph loop

Max **5** modify/test iterations **per eval**, then **throw the eval
out**. Do not pile on lucky keywords to force a split.

One eval per loop.

1. Inspect what the blank **actually filed**.
2. Set `must_not_find` to the out-of-dimension bait it used and the
   specialist is told to skip. Prefer **one distinctive token**.
3. If the blank had nothing out-of-scope to file, add unused-helper
   bait to the fixture, then re-run **custom** (fixture changed).
4. Re-score the **frozen** blank transcript — must **FAIL**
   `score_behavior`.
5. Re-score custom / golden — must **PASS**. If the fixture or spec
   changed, **re-run the live custom agent**, not only the golden.
6. Log the iteration in `agents/<name>/evals/ralph-loop.md`
   (what failed, what changed, keep vs throw out).

After a keep: freeze the blank JSON under
`agents/<name>/evals/blank_runs/` and assert
`test_blank_agent_transcript_fails_behavior_score` (or equivalent)
fails `score_behavior`.

### Keep vs throw

```
blank PASSES behavior, or FAIL is synonym-only
        → retune (bait / one-token must_not_find)
blank FAILS behavior on the bait AND live custom PASSES full score
        → keep, freeze transcript, add pytest
5 iters, still no split
        → delete the eval
```

## After any edit

If you touched the fixture or `evals.json`:

1. Re-score every frozen blank with `score_behavior` (must fail).
2. Re-run the **live** custom agent (must pass full score).
3. Update the golden only after the live custom still passes.
4. Append the Ralph log.

Scoring goldens alone does not prove a live custom agent still omits
the bait.

## Common mistakes

| Excuse | Reality |
| --- | --- |
| "Blank failed the full scorer, so we are done" | It failed identity / schema. Check `score_behavior`. |
| "must_find drain / camel — blank said release / PascalCase" | Synonym miss, not differentiation. Use fixture words. |
| "must_not_find needs rename _tmp AND poor comment" | Blank filed the nit without that pair. One token. |
| "I shortened the blank JSON for the fixture" | Paraphrase rewrites tokens and corrupts the transcript. Save verbatim. |
| "Golden still passes after tightening" | Goldens are written to pass. Re-run the live custom agent. |
| "Custom peeked at evals.json once; faster" | Eval subjects must not read evals, goldens, or ralph-loop.md. |
| "Retune every eval from this blank's wording" | One eval per Ralph loop. |
| "One more keyword will split it" | Cap 5. Then delete the eval. |
| "Skip the bait; the bug is enough" | Any competent agent finds the obvious bug. |
| "Guess must_not_find before the blank runs" | Use what the blank actually wrote. |

## Red flags — stop

- Blank passes `score_behavior` and the eval is still marked keep
- Split exists only on `agent` / full schema, not behavior
- `must_find` is specialist vocabulary absent from the fixture
- `must_not_find` is an AND of phrases the blank never uttered
- Blank transcript was rewritten before scoring
- Custom or blank read `evals.json` / goldens / `ralph-loop.md`
- Fixture changed and only the golden was re-scored
- Ralph iter 6 on the same eval
- Same blank wording copied into every eval's `must_not_find`

## Definition of done

- One loud out-of-scope bait is in the fixture
- `must_find` uses fixture defect words; `must_not_find` is one
  empirical token (or orchestrator groups are a real grouping split)
- Live custom passes **full** score; frozen blank fails
  **`score_behavior`**
- Verbatim blank JSON is in `blank_runs/` with a pytest
- Ralph log updated (keep vs throw); no eval kept past 5 failed iters
- Neither subject read evals / goldens / ralph-loop.md
