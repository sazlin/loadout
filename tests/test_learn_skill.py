"""Contracts and colocated evals for the /learn skill on the base loadout."""

from __future__ import annotations

import json
from pathlib import Path

from loadout.frontmatter import parse_skill_md
from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO / "skills" / "learn"
SKILL_MD = SKILL_ROOT / "SKILL.md"
LEARNINGS_CAP = 20
CAP_FIXTURE = SKILL_ROOT / "evals" / "files" / "agents-at-cap.md"


def _evals_payload() -> dict[str, object]:
    path = SKILL_ROOT / "evals" / "evals.json"
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


def _numbered_learnings(text: str) -> list[str]:
    _, _, rest = text.partition("## Learnings")
    section, _, _ = rest.partition("<!-- BEGIN LOADOUT:")
    items: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        prefix, _, remainder = stripped.partition(". ")
        if prefix.isdigit() and remainder:
            items.append(stripped)
    return items


def test_learn_skill_parses() -> None:
    assert SKILL_MD.is_file(), SKILL_MD
    parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name="learn")


def test_base_loadout_includes_learn() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert "skills/learn" in srcs


def test_learn_description_is_command_triggered() -> None:
    meta = parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name="learn")
    lowered = meta.description.lower()
    assert "/learn" in lowered
    assert "only" in lowered
    remainder = lowered.replace("/learn", "")
    assert "implement" in remainder or "passing" in remainder


def test_learn_body_reflects_then_lists_mistakes_then_derives_rules() -> None:
    text = SKILL_MD.read_text()
    lowered = text.lower()
    assert "/learn" in lowered
    assert "session" in lowered
    assert "mistake" in lowered
    assert "subagent" in lowered
    assert "obvious" in lowered
    assert "high confidence" in lowered or "high-confidence" in lowered
    assert "project-level" in lowered or "project level" in lowered
    steps, _, _ = text.partition("## Common mistakes")
    steps_lower = steps.lower()
    reflect = steps_lower.index("reflect")
    enumerate_at = min(
        i
        for i in (
            steps_lower.find("enumerate"),
            steps_lower.find("list the"),
            steps_lower.find("concise list"),
        )
        if i >= 0
    )
    derive = min(i for i in (steps_lower.find("derive"), steps_lower.find("mitigate")) if i >= 0)
    assert reflect < enumerate_at < derive


def test_learn_body_creates_or_merges_agents_learnings() -> None:
    text = SKILL_MD.read_text()
    lowered = text.lower()
    assert "agents.md" in lowered
    assert "## learnings" in lowered
    assert "preamble" in lowered or "dynamic learnings" in lowered
    assert "merge" in lowered
    assert "dedupe" in lowered or "de-dupe" in lowered or "deduplicate" in lowered
    assert "numbered" in lowered
    assert "create" in lowered


def test_learn_body_skips_generated_block_and_does_not_invent() -> None:
    text = SKILL_MD.read_text()
    lowered = text.lower()
    assert "generated" in lowered
    assert "do not invent" in lowered or "don't invent" in lowered or "do not fabricate" in lowered
    assert "unchanged" in lowered or "no obvious" in lowered


def test_learn_has_colocated_evals() -> None:
    payload = _evals_payload()
    assert payload["skill_name"] == "learn"
    evals = payload.get("evals")
    assert isinstance(evals, list) and evals
    for index, entry in enumerate(evals):
        assert isinstance(entry, dict)
        files = entry.get("files")
        if not isinstance(files, list):
            continue
        for relative in files:
            assert isinstance(relative, str)
            path = SKILL_ROOT / relative
            assert path.is_file(), f"learn evals[{index}] missing {relative}"


def test_learn_evals_cover_create_merge_empty_subagent_and_command_only() -> None:
    texts = _eval_texts(_evals_payload())
    assert "/learn" in texts
    assert "learnings" in texts
    assert "merge" in texts or "dedupe" in texts or "de-dupe" in texts
    assert "no obvious" in texts or "no mistakes" in texts or "clean session" in texts
    assert "subagent" in texts
    assert "generated" in texts or "do not edit" in texts
    assert "passing" in texts or "implement" in texts


def test_learn_body_caps_numbered_learnings_and_prunes() -> None:
    text = SKILL_MD.read_text()
    lowered = text.lower()
    assert str(LEARNINGS_CAP) in text
    assert "prune" in lowered
    assert "improve" in lowered and "in place" in lowered
    assert "unbounded" in lowered or "exceed" in lowered


def test_learn_body_leaves_agents_unchanged_when_no_durable_rules() -> None:
    text = SKILL_MD.read_text()
    lowered = text.lower()
    assert "unchanged" in lowered
    assert "high-confidence" in lowered or "high confidence" in lowered
    assert "session-specific" in lowered


def test_learn_cap_fixture_has_exactly_cap_numbered_items() -> None:
    assert CAP_FIXTURE.is_file(), CAP_FIXTURE
    items = _numbered_learnings(CAP_FIXTURE.read_text())
    assert len(items) == LEARNINGS_CAP


def test_learn_evals_cover_cap_prune_and_session_specific_noop() -> None:
    texts = _eval_texts(_evals_payload())
    assert str(LEARNINGS_CAP) in texts
    assert "prune" in texts or "cap" in texts
    assert "session-specific" in texts or "one-off" in texts
    assert "unchanged" in texts
