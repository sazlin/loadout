# Davinci simplification judge rubric

Score each dimension from **1** (no improvement / regression) to **10** (excellent simplification).
Behavior must be preserved; penalize any functional change or deleted assertions.

## Dimensions

1. **smell_removal** — How many targeted AI smells were actually removed (abstractions, factories, defensive noise, narration)?
2. **behavior_preservation** — Does the simplified code still pass the original `__main__` assertions unchanged?
3. **readability** — Is the result easier to read without adding new indirection?
4. **proportionality** — Edits are focused; no drive-by refactors or new abstractions.
5. **python_idioms** — Uses plain dataclasses/functions where appropriate; no new ceremony.

## Output

Respond with **only** a JSON object:

```json
{
  "scores": {
    "smell_removal": 0,
    "behavior_preservation": 0,
    "readability": 0,
    "proportionality": 0,
    "python_idioms": 0
  },
  "overall": 0,
  "notes": "One or two sentences on what improved and what was missed."
}
```

`overall` is the rounded mean of the five dimension scores.
