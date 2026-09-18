"""Contracts and colocated evals for pr_review_harness skills."""

from __future__ import annotations

import json
import re
from pathlib import Path

from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"
PR_REVIEW_SKILLS = (
    "dispatch-panel-review",
    "dedupe-and-write-tasks",
    "resolve-next-task",
    "dispatch-resolve-wave",
    "log-progress",
    "dispatch-verifiers",
)


def test_pr_review_skills_have_colocated_evals() -> None:
    for name in PR_REVIEW_SKILLS:
        evals = SKILLS / name / "evals" / "evals.json"
        assert evals.is_file(), evals
        data = json.loads(evals.read_text())
        assert data["skill_name"] == name
        for index, entry in enumerate(data["evals"]):
            for relative in entry.get("files", []):
                path = SKILLS / name / relative
                assert path.is_file(), f"{name} evals[{index}] missing {relative}"


def test_resolve_next_task_eval_uses_hashed_tasks_fixture() -> None:
    evals = json.loads((SKILLS / "resolve-next-task" / "evals" / "evals.json").read_text())
    entry = evals["evals"][0]
    assert entry["files"] == ["evals/files/TASKS_TO_RESOLVE-abc1234.md"]
    assert "tasks_path" in entry["prompt"].lower()
    assert "TASKS_TO_RESOLVE-abc1234.md" in entry["prompt"]


def test_pr_review_skill_bodies_encode_harness_contracts() -> None:
    panel = (SKILLS / "dispatch-panel-review" / "SKILL.md").read_text().lower()
    assert "parallel" in panel
    assert "review_correctness" in panel
    assert "in-process" in panel or "in process" in panel
    assert "not fast" in panel
    assert "effort=medium" in panel
    assert "composer-2.5" not in panel
    assert "loop 2" in panel or "loop 2+" in panel or "loops 2" in panel
    assert "issue_resolver" in panel or "resolver commit" in panel
    assert "all four" in panel or "four reviewers" in panel

    dedupe = (SKILLS / "dedupe-and-write-tasks" / "SKILL.md").read_text()
    assert "TASKS_TO_RESOLVE-" in dedupe
    assert "1-3" in dedupe or "1–3" in dedupe
    assert "brief" in dedupe.lower()
    dedupe_lower = dedupe.lower()
    assert "minor" in dedupe_lower
    assert "never" in dedupe_lower and "open task" in dedupe_lower
    assert "critical" in dedupe_lower and "important" in dedupe_lower
    assert "review_history.md" in dedupe_lower or "panel comment" in dedupe_lower
    for key in ("id", "title", "severity", "file"):
        assert f"`{key}`" in dedupe

    resolve = (SKILLS / "resolve-next-task" / "SKILL.md").read_text().lower()
    assert "git push" in resolve
    assert "merge" in resolve
    assert "tasks_to_resolve-" in resolve
    assert "do not delete" in resolve or "never delete" in resolve
    assert "do not edit" in resolve or "never edit" in resolve
    assert "review_history.md" in resolve
    assert "do not mark" in resolve or "never mark" in resolve

    history = (SKILLS / "log-progress" / "SKILL.md").read_text()
    assert "REVIEW_HISTORY.md" in history
    assert "append" in history.lower()
    assert "30 days" in history.lower()
    assert "review_orchestrator" in history.lower()
    assert "aborted" in history.lower()
    assert "deferred minor" in history.lower() or "deferred_minors" in history.lower()
    assert "deferred minors:" in history.lower()
    assert "summary paragraph" in history.lower()
    assert (SKILLS / "log-progress" / "scripts" / "trim_review_history.py").is_file()
    template = (SKILLS / "log-progress" / "references" / "review-history-template.md").read_text()
    assert "aborted" in template.lower()
    assert "id (title)" in template
    assert "deferred_minors[]" in template
    assert "display form" in template.lower()

    verifiers = (SKILLS / "dispatch-verifiers" / "SKILL.md").read_text()
    assert "VERIFIERS.md" in verifiers
    lowered = verifiers.lower()
    assert "empty" in lowered
    assert "never create" in lowered or "never creates" in lowered
    assert "true" in lowered and "false" in lowered
    assert "composer-2.5" in lowered


def test_dispatch_resolve_wave_skill_encodes_parallel_wave_contract() -> None:
    source = (SKILLS / "dispatch-resolve-wave" / "SKILL.md").read_text()
    vendored = (REPO / ".claude" / "skills" / "dispatch-resolve-wave" / "SKILL.md").read_text()
    for text in (source, vendored):
        skill = text.lower()
        assert "partition_waves.py" in skill
        assert "wave cap" in skill or "cap 4" in skill or "max 4" in skill
        assert "worktree" in skill
        assert "cherry-pick" in skill
        assert "same turn" in skill or "single" in skill and "parallel" in skill
        assert "origin/<pr-head>" in skill or "pr head" in skill
        assert "do not implement" in skill or "do not become" in skill
        assert "old path" not in skill
        assert "git checkout" in skill
        assert "pr worktree" in skill
        assert "git fetch" in skill
        assert "before" in skill
        assert "every wave" in skill
        assert "dispatch failure" in skill
        assert "git worktree remove" in skill
        assert "never push" in skill and "origin/<pr-head>" in skill
        assert "orchestrator pushes after successful picks" in skill
        assert "not the whole wave" in skill
        assert "fourth identical parallel wave" in skill
        assert "integrate" not in skill


def _numbered_skill_steps(text: str) -> dict[int, str]:
    steps: dict[int, str] = {}
    current: int | None = None
    chunks: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^(\d+)\.\s+(.*)", line)
        if match:
            if current is not None:
                steps[current] = " ".join(chunks)
            current = int(match.group(1))
            chunks = [match.group(2)]
            continue
        if current is None:
            continue
        if line.startswith("## "):
            steps[current] = " ".join(chunks)
            break
        chunks.append(line)
    if current is not None and current not in steps:
        steps[current] = " ".join(chunks)
    return steps


def test_dispatch_resolve_wave_copies_gitignored_tasks_file_into_each_worktree() -> None:
    source = (SKILLS / "dispatch-resolve-wave" / "SKILL.md").read_text()
    vendored = (REPO / ".claude" / "skills" / "dispatch-resolve-wave" / "SKILL.md").read_text()
    for text in (source, vendored):
        skill = text.lower()
        assert "copy" in skill
        assert "tasks_path" in skill
        assert "frozen" in skill
        assert "gitignored" in skill
        assert "absolute" in skill
        assert "git cwd" in skill
        worktree_step = next(
            body for body in _numbered_skill_steps(text).values() if "git worktree add" in body.lower()
        )
        lowered = worktree_step.lower()
        assert "/tmp" in lowered
        assert "copy" in lowered
        assert "tasks_path" in lowered


def test_dispatch_resolve_wave_splits_setup_fallback_and_parallel_dispatch() -> None:
    source = (SKILLS / "dispatch-resolve-wave" / "SKILL.md").read_text()
    vendored = (REPO / ".claude" / "skills" / "dispatch-resolve-wave" / "SKILL.md").read_text()
    for text in (source, vendored):
        steps = _numbered_skill_steps(text)
        worktree_n, worktree = next((n, body) for n, body in steps.items() if "git worktree add" in body.lower())
        parallel_n, parallel = next(
            (n, body) for n, body in steps.items() if "all wave resolvers in one turn" in body.lower()
        )
        partial_n = next(n for n, body in steps.items() if "do not stop the whole wave" in body.lower())
        assert worktree_n != parallel_n
        assert partial_n != parallel_n
        assert worktree_n != partial_n
        assert "all wave resolvers in one turn" not in worktree.lower()
        assert "cherry-pick" not in worktree.lower()
        assert "isolated checkout" in parallel.lower() or "isolated dir" in parallel.lower()
        assert "every wave task" in parallel.lower()


def test_dispatch_resolve_wave_prunes_worktrees_after_conflict_and_abort() -> None:
    source = (SKILLS / "dispatch-resolve-wave" / "SKILL.md").read_text()
    vendored = (REPO / ".claude" / "skills" / "dispatch-resolve-wave" / "SKILL.md").read_text()
    for text in (source, vendored):
        skill = text.lower()
        assert "conflict abort" in skill or "cherry-pick --abort" in skill
        assert "missing sha" in skill
        assert "git worktree remove --force" in skill
        assert "git worktree prune" in skill
        assert "abort-if-merged" in skill
        assert "resolve-loop exit" in skill
        assert "reuse" in skill
        assert "reset" in skill
        assert "do not stop the whole wave" in skill
        assert "/tmp/pr-resolve-" in skill
        cleanup = next(
            body.lower() for body in _numbered_skill_steps(text).values() if "git worktree prune" in body.lower()
        )
        assert "conflict" in cleanup
        assert "missing sha" in cleanup


def test_resolve_next_task_does_not_push_pr_head() -> None:
    resolve = (SKILLS / "resolve-next-task" / "SKILL.md").read_text().lower()
    assert "task branch" in resolve
    assert "do not push" in resolve or "never push" in resolve
    assert "pr head" in resolve or "pr-head" in resolve or "pr branch" in resolve
    assert "tasks_to_resolve-" in resolve
    assert "review_history.md" in resolve
    assert "git checkout" in resolve
    assert "pr worktree" in resolve


def test_pr_review_skills_are_not_orphans() -> None:
    loadout = load_loadout(REPO / "loadouts" / "pr_review_harness.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert {f"skills/{name}" for name in PR_REVIEW_SKILLS} == srcs


def test_gitignore_covers_ephemeral_tasks_files() -> None:
    text = (REPO / ".gitignore").read_text()
    assert "/TASKS_TO_RESOLVE.md" in text
    assert "/TASKS_TO_RESOLVE-*.md" in text
    assert ".worktrees/" in text
