# Review history

Append-only log for the PR-review harness. `review_orchestrator` drops
entries older than 30 days after a run's other tasks complete.

## <ISO timestamp> — <agent> — <phase>

- **Task:** <TASK-NNN or none>
- **Outcome:** ok | blocked | false_claim | merged | wait_for_human | aborted
- **Deferred minors:** none | id (title), …
- **Summary:** <one paragraph>

`id (title)` is the display form of each `deferred_minors[]` object
(`id`, `title`, `severity`, `file`), not a second schema. Put ids only on
**Deferred minors:**, not again in **Summary**.
