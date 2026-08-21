---
name: learn
description: >-
  Use only when the user says /learn or asks to capture this session's
  agent mistakes as project learnings in AGENTS.md. Do not use while
  implementing, reviewing, or mentioning a mistake in passing.
---

# Learn

Command only. Turn obvious agent (and subagent) mistakes from this session
into short project-level rules in `AGENTS.md`.

A **mistake** is something the agent or a subagent got wrong: skipped a
required check, edited the wrong place, ignored a rule, claimed tests
passed without running them, repeated a failed approach. Mechanical steps
and user errors are not mistakes. Vague "be more careful" advice is not a
rule.

## Steps

1. **Reflect** on this session (conversation, tool results, diffs, and every
   **subagent**) and identify **obvious** mistakes only.
2. **Enumerate** those mistakes in a **concise list** in the reply. If none,
   say there were **no obvious** mistakes, leave `AGENTS.md` **unchanged**,
   and stop. **Do not invent** mistakes.
3. **Derive** a short list of concise **project-level** rules that with
   **high confidence** will substantially **mitigate** repeating one or more
   of those mistakes. Drop low-confidence or session-specific nits.
4. Inspect project-root `AGENTS.md` for a `## Learnings` section (create the
   file if missing):
   - No section → **create** `## Learnings` in the hand-owned region,
     **before** any `<!-- BEGIN LOADOUT:` **generated** block, with a
     **preamble** that these are **dynamic learnings** an agent should
     consider, then a **numbered** list of the new rules.
   - Section exists → **merge** the new rules into the current list.
     **Dedupe** by meaning (not exact text), improve an existing rule when
     the new wording is strictly better, keep unrelated items, then
     renumber.
   Never edit text inside generated loadout markers (`<!-- BEGIN LOADOUT:`
   … `<!-- END LOADOUT:`). Do not rewrite the rest of `AGENTS.md`. Do not
   commit unless asked.

## Reply recipe

```
# Session mistakes

1. <one line>
2. ...

# Learnings

Wrote `AGENTS.md` ## Learnings:
1. <rule added or improved>
...
```

## Common mistakes

| Temptation | Do this instead |
| --- | --- |
| Invent misses on a clean session | Say no obvious mistakes; leave the file unchanged |
| Vague rules ("be careful", "always test") | High-confidence, specific, project-level |
| Second `## Learnings` heading | Merge into the existing section |
| Edit the generated loadout block | Hand-owned region only |
| Skip subagent transcripts | Include obvious subagent mistakes |
| Trigger on "that was a mistake" mid-task | Command only |
