---
name: next-decision
description: >-
  Use only when the user says /next-decision or /next-decision with a
  decision id (D1, D2, or a number). Do not use while implementing,
  listing decisions, or discussing a choice in passing.
---

# Next-decision

Command only. Follows **decisions**. Review **one** listed decision so a human can judge whether it was the right call.

This is not "the next decision to make". Listed choices are not "already done" — they still need review.

## Steps

1. If `.session-decisions.md` is missing, follow **decisions** first, then continue. If this session already has a grok list, reuse it when writing the file instead of requiring a second scan — do not use "has a list" as a reason to skip file creation. After that write, pick `next:` as in step 2 (D1 if missing).
2. Pick the target:
   - `/next-decision` → the id in `next:` (D1 if missing)
   - `/next-decision D2` or `/next-decision 2` → that id
3. If the user passed no id and `next:` is `done`, say every listed decision has been reviewed. Stop. Do not treat `done` as a decision id.
4. If the list is empty or the id is unknown, say so. Stop.
5. Write **one** review using the recipe below. No other decisions.
6. If the user passed no id (bare `/next-decision`), set `next:` to the id after the one just reviewed, or `done` if none remain. If the user passed `D<n>` / `n`, leave `next:` unchanged unless that id equals the current `next:` value, in which case advance it the same way. Do not commit `.session-decisions.md`.

## Review recipe

```
## D<n>: <short title>

**Choice:** what was selected
**Alternatives:** what else was on the table, or "none considered"
**Why:** the reason given at the time
**Stakes:** what this affects (files, API, scope) and how reversible it is
**Trade-offs:** costs and risks
**Review point:** one sentence a human can agree or disagree with
```

Enough to judge the call. Not a session recap. Not a one-line restatement. Not an offer to reverse unless they ask.

## Common mistakes

| Temptation | Do this instead |
| --- | --- |
| "Nothing next — those are already done" | Review the next listed choice |
| Treat `/next-decision` as future work | Review a past choice from the list |
| Dump every decision in full | One id this run |
| One-line restatement | Full recipe |
| Trigger on "we decided X" mid-task | Command only |
