# Ralph loop: implementation_orchestrator

Goal: fail a blank coordinator that opens a draft and starts review_orchestrator.

Blank iter 0 used --draft and review_orchestrator. Keep.

Blocked-plan eval: a blank that still runs build-implementation-plan / imp_builder
and emits status ok after a blocked planner report fails must_find
`"status": "blocked"` and hits must_not_find build tokens. Keep.
