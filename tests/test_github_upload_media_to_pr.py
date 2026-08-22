"""Contracts and colocated evals for the github-upload-media-to-pr skill."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loadout.frontmatter import parse_skill_md
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO / "skills" / "github-upload-media-to-pr"
SKILL_MD = SKILL_ROOT / "SKILL.md"
SKILL_NAME = "github-upload-media-to-pr"


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


def test_github_upload_media_skill_parses() -> None:
    assert SKILL_MD.is_file(), SKILL_MD
    meta = parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name=SKILL_NAME)
    assert meta.name == SKILL_NAME
    assert meta.license == "MIT"


def test_github_loadout_ships_upload_media_skill() -> None:
    loadout = load_loadout(REPO / "loadouts" / "github.yaml")
    assert loadout.name == "github"
    assert loadout.extends == ["base"]
    assert {entry["src"] for entry in loadout.skills} == {f"skills/{SKILL_NAME}"}
    assert loadout.rules == []
    assert loadout.agents == []
    assert loadout.mcps == []


def test_base_loadout_does_not_include_github_upload_media_skill() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert f"skills/{SKILL_NAME}" not in srcs


def test_description_triggers_on_media_and_pr_phrases() -> None:
    meta = parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name=SKILL_NAME)
    lowered = meta.description.lower()
    assert "pull request" in lowered or "pr" in lowered
    assert "screenshot" in lowered
    assert "video" in lowered or "recording" in lowered
    assert "put the screenshot in the pr" in lowered


def test_body_uses_cursor_cloud_attach_not_agent_browser() -> None:
    text = SKILL_MD.read_text()
    lowered = text.lower()
    assert "managepullrequest" in lowered
    assert "/opt/cursor/artifacts/" in lowered
    assert "computeruse" in lowered
    assert "recordscreen" in lowered
    assert "<img" in lowered
    assert "<video" in lowered
    assert "npx skills add" in lowered
    assert "npm i -g agent-browser" in lowered
    assert "do not" in lowered
    assert "gh pr comment" in lowered
    assert "gh pr edit" in lowered


def test_body_does_not_instruct_installing_agent_browser() -> None:
    text = SKILL_MD.read_text()
    lowered = text.lower()
    install_needles = (
        "npx skills add vercel-labs/agent-browser -g -y",
        "npm i -g agent-browser && agent-browser install",
    )
    for needle in install_needles:
        assert needle in lowered
    do_not, _, _ = lowered.partition("## do not")
    assert "npx skills add vercel-labs/agent-browser" not in do_not
    assert "npm i -g agent-browser && agent-browser install" not in do_not


def test_has_colocated_evals() -> None:
    payload = _evals_payload()
    assert payload["skill_name"] == SKILL_NAME
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
            assert path.is_file(), f"{SKILL_NAME} evals[{index}] missing {relative}"


def test_evals_cover_img_video_and_install_refusal() -> None:
    texts = _eval_texts(_evals_payload())
    assert "/opt/cursor/artifacts/" in texts
    assert "managepullrequest" in texts
    assert "img" in texts
    assert "video" in texts
    assert "post_comment" in texts
    assert "npx skills add" in texts
    assert "npm i -g" in texts
    assert "does not run" in texts or "refuse" in texts


def test_github_sync_vendors_skill_without_evals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [github]\n")
    sync(project)
    dest = project / ".claude/skills" / SKILL_NAME / "SKILL.md"
    assert dest.is_file()
    assert "ManagePullRequest" in dest.read_text()
    assert not (project / ".claude/skills" / SKILL_NAME / "evals").exists()
    assert (project / ".claude/agents/davinci.md").is_file()


def test_base_sync_does_not_vendor_github_upload_media_skill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [base]\n")
    sync(project)
    assert not (project / ".claude/skills" / SKILL_NAME).exists()
