"""Contracts and colocated evals for session decision-review skills."""

from __future__ import annotations

import json
from pathlib import Path

from loadout.frontmatter import parse_skill_md
from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"
DECISIONS = SKILLS / "decisions"
NEXT_DECISION = SKILLS / "next-decision"


def _evals_payload(skill_root: Path) -> dict[str, object]:
    path = skill_root / "evals" / "evals.json"
    assert path.is_file(), path
    payload = json.loads(path.read_text())
    assert isinstance(payload, dict)
    return payload


def _eval_texts(payload: dict[str, object]) -> str:
    raw = payload.get("evals")
    if not isinstance(raw, list):
        return ""
    chunks: list[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        chunks.append(str(entry.get("prompt", "")))
        chunks.append(str(entry.get("expected_output", "")))
        expectations = entry.get("expectations")
        if isinstance(expectations, list):
            chunks.extend(str(item) for item in expectations)
    return "\n".join(chunks).lower()


def test_decisions_and_next_decision_skills_parse() -> None:
    for root in (DECISIONS, NEXT_DECISION):
        skill_md = root / "SKILL.md"
        assert skill_md.is_file(), skill_md
        parse_skill_md(skill_md, skill_md.read_text(), dir_name=root.name)


def test_base_loadout_includes_session_decision_skills() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert "skills/decisions" in srcs
    assert "skills/next-decision" in srcs


def test_decisions_body_lists_grok_lines_not_status() -> None:
    text = (DECISIONS / "SKILL.md").read_text()
    lowered = text.lower()
    assert "/decisions" in lowered
    assert "chronological" in lowered
    assert "d1" in lowered
    assert ".session-decisions.md" in lowered
    assert "grok" in lowered
    assert "mechanical" in lowered or "not a decision" in lowered
    assert "next-decision" in lowered
    assert "do not commit" in lowered or "don't commit" in lowered


def test_next_decision_body_reviews_one_listed_choice() -> None:
    text = (NEXT_DECISION / "SKILL.md").read_text()
    lowered = text.lower()
    assert "command only" in lowered
    assert "/next-decision" in lowered
    assert "d2" in lowered or "decision id" in lowered
    assert "/decisions" in lowered
    assert "alternatives" in lowered
    assert "one" in lowered
    assert "already done" in lowered or "next decision to make" in lowered
    assert ".session-decisions.md" in lowered


def test_next_decision_description_is_command_only() -> None:
    skill_md = NEXT_DECISION / "SKILL.md"
    meta = parse_skill_md(skill_md, skill_md.read_text(), dir_name="next-decision")
    lowered = meta.description.lower()
    assert "/next-decision" in lowered
    assert "only" in lowered
    assert "/decisions" not in lowered or "do not" in lowered


def test_session_decision_skills_have_colocated_evals() -> None:
    for name, root in (("decisions", DECISIONS), ("next-decision", NEXT_DECISION)):
        payload = _evals_payload(root)
        assert payload["skill_name"] == name
        evals = payload.get("evals")
        assert isinstance(evals, list) and evals
        for index, entry in enumerate(evals):
            assert isinstance(entry, dict)
            files = entry.get("files")
            if not isinstance(files, list):
                continue
            for relative in files:
                assert isinstance(relative, str)
                path = root / relative
                assert path.is_file(), f"{name} evals[{index}] missing {relative}"


def test_decisions_rewrite_step_names_d_sections_and_preserves_next_by_grok_line() -> None:
    text = (DECISIONS / "SKILL.md").read_text()
    steps, _, _ = text.partition("## Reply recipe")
    lowered = steps.lower()
    assert "## d" in lowered
    assert "next:" in lowered
    assert "grok headings" not in lowered
    assert "grok-line" in lowered or "grok line" in lowered
    assert "done" in lowered


def test_decisions_evals_cover_grok_list_not_transcript() -> None:
    texts = _eval_texts(_evals_payload(DECISIONS))
    assert "/decisions" in texts
    assert "d1" in texts
    assert "mechanical" in texts or "ran tests" in texts or "read " in texts


def test_decisions_evals_preserve_next_by_grok_line_after_rewrite() -> None:
    texts = _eval_texts(_evals_payload(DECISIONS))
    assert "postgres" in texts
    assert "next: done" in texts
    assert "grok-line" in texts or "grok line" in texts
    assert "skip harness" in texts
    assert "yagni" in texts


def test_next_decision_evals_cover_cursor_and_id_arg() -> None:
    texts = _eval_texts(_evals_payload(NEXT_DECISION))
    assert "/next-decision" in texts
    assert "d2" in texts
    assert "already" in texts or "next decision to make" in texts or "future" in texts


def test_next_decision_rebuilds_missing_file_even_with_in_session_list() -> None:
    text = (NEXT_DECISION / "SKILL.md").read_text()
    steps, _, _ = text.partition("## Review recipe")
    lowered = steps.lower()
    assert "`.session-decisions.md` is missing" in lowered
    assert "missing and this session has no" not in lowered
    assert "reuse" in lowered
    assert "grok list" in lowered


def test_next_decision_done_short_circuit_is_no_id_only() -> None:
    text = (NEXT_DECISION / "SKILL.md").read_text()
    steps, _, _ = text.partition("## Review recipe")
    lowered = steps.lower()
    no_id_done = lowered.index("passed no id")
    unknown = lowered.index("unknown")
    assert no_id_done < unknown
    assert "every listed" in lowered
    assert "do not treat `done` as a decision id" in lowered
    assert "the target was `next:`" not in steps
    assert "bare `/next-decision`" in lowered
    assert "leave `next:` unchanged" in lowered
    assert "current `next:` value" in lowered


def test_next_decision_evals_cover_done_no_arg_explicit_id_and_missing_file() -> None:
    texts = _eval_texts(_evals_payload(NEXT_DECISION))
    assert "next: done" in texts
    assert "/next-decision d2" in texts
    assert "unknown" in texts
    assert "no .session-decisions.md" in texts
    assert "grok list" in texts
