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

1. If `.session-decisions.md` is missing and this session has no decisions list, follow **decisions** first, then continue.
2. Pick the target:
   - `/next-decision` → the id in `next:` (D1 if missing)
   - `/next-decision D2` or `/next-decision 2` → that id
3. If the list is empty or the id is unknown, say so. Stop.
4. If `next:` is `done`, say every listed decision has been reviewed. Stop.
5. Write **one** review using the recipe below. No other decisions.
6. If the target was `next:`, set `next:` to the following id (or `done`). An explicit-id review does not move `next:` unless it matches. Do not commit `.session-decisions.md`.

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
