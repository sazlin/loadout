# Review history

Append-only log for the PR-review harness. `review_orchestrator` drops
entries older than 30 days after a run's other tasks complete.

## <ISO timestamp> — <agent> — <phase>

- **Task:** <TASK-NNN or none>
- **Outcome:** ok | blocked | false_claim | merged | wait_for_human
- **Summary:** <one paragraph>
