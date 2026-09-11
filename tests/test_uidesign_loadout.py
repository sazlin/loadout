"""Contracts for the uidesign loadout and vendored SkillUI consumer skill."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from loadout.frontmatter import parse_skill_md
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
SKILL_NAME = "skillui"
SKILL_SRC = f"skills/{SKILL_NAME}"
SKILL_ROOT = REPO / SKILL_SRC
SKILL_MD = SKILL_ROOT / "SKILL.md"
UPSTREAM = "https://github.com/amaancoderx/npxskillui"
UPSTREAM_COMMIT = "bc913a8d3503d6b2a683e4a3ac04ffe7304ac510"
SKILLUI_VERSION = "1.3.4"
SKILLUI_PACKAGE = f"skillui@{SKILLUI_VERSION}"
UNPINNED_NPX_SKILLUI = re.compile(rf"npx(?:\s+-y|\s+--yes)?\s+skillui(?!@{re.escape(SKILLUI_VERSION)})")
CURL_PIPE_SH = re.compile(r"curl[^\n]*\|\s*(?:ba)?sh")
# Consumer-skill needles: prose install lines that SOURCE.md says to strip
# on bump (not typos). Not Stripe `Bash(...)` grants.
FORBIDDEN_INSTALL_SUBSTRINGS = (
    "npm i -g skillui",
    "npm install -g skillui",
    "npm i -g playwright",
    "npm install -g playwright",
    "npx skills add",
)
# Tree-wide command phrases with refusal exemptions; not a replacement for
# FORBIDDEN_INSTALL_SUBSTRINGS (SKILL.md-only, no exemptions, exact grant strings).
EXECUTABLE_INSTALL_NEEDLES = (
    "npm i -g",
    "npm install -g",
    "npx skills add",
    "curl | sh",
)
_REFUSAL_MARKERS = ("do not run", "does not run", "does not auto-run", "do not execute")


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def _silence_cli_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("loadout.sync.run_cli_tools", lambda tools, project_root: None)


def _executable_install_hits(text: str) -> list[str]:
    hits: list[str] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        previous = lines[index - 1] if index else ""
        window = " ".join(f"{previous} {line}".split()).lower()
        if any(marker in window for marker in _REFUSAL_MARKERS):
            continue
        for needle in EXECUTABLE_INSTALL_NEEDLES:
            if needle in line:
                hits.append(f"{needle!r} in {line.strip()!r}")
    return hits


def test_executable_install_hits_treats_refusals_as_non_hits() -> None:
    assert _executable_install_hits("npm i -g skillui\n")
    assert not _executable_install_hits("Do not run `npm i -g skillui`.\n")
    collide = "that does not collide with loadout-managed skills\nnpm i -g skillui"
    assert _executable_install_hits(collide)


def test_uidesign_loadout_ships_skillui_skill_and_cli() -> None:
    loadout = load_loadout(REPO / "loadouts" / "uidesign.yaml")
    assert loadout.name == "uidesign"
    assert loadout.extends == []
    assert {entry["src"] for entry in loadout.skills} == {SKILL_SRC}
    assert loadout.rules == []
    assert loadout.agents == []
    assert loadout.mcps == []
    assert loadout.hooks == []
    assert len(loadout.cli_tools) == 1
    tool = loadout.cli_tools[0]
    assert tool.name == "skillui"
    assert SKILLUI_PACKAGE in tool.command
    assert "npm install -D" in tool.command
    assert "npm install -g" not in tool.command
    assert "--version" in tool.command
    assert f"grep -q {SKILLUI_VERSION}" in tool.command
    assert "| sh" not in tool.command
    assert "|sh" not in tool.command.replace(" ", "")


def test_base_loadout_does_not_include_skillui() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert SKILL_SRC not in srcs


def test_skillui_skill_parses() -> None:
    assert SKILL_MD.is_file(), SKILL_MD
    meta = parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name=SKILL_NAME)
    assert meta.name == SKILL_NAME
    assert meta.license == "MIT"
    lowered = meta.description.lower()
    assert "skillui" in lowered or "npxskillui" in lowered
    assert "design" in lowered
    data = yaml.safe_load(SKILL_MD.read_text().split("---", 2)[1])
    assert "<" not in data["description"]
    assert ">" not in data["description"]


def test_skillui_skill_evals_are_colocated() -> None:
    evals = SKILL_ROOT / "evals" / "evals.json"
    payload = json.loads(evals.read_text())
    assert payload["skill_name"] == SKILL_NAME
    assert payload["evals"]
    for index, entry in enumerate(payload["evals"]):
        for relative in entry.get("files", []):
            path = REPO / SKILL_SRC / relative
            assert path.is_file(), f"evals[{index}] missing {relative}"


def test_skillui_source_pins_npxskillui() -> None:
    source = (SKILL_ROOT / "SOURCE.md").read_text()
    assert UPSTREAM in source
    assert UPSTREAM_COMMIT in source
    assert SKILLUI_VERSION in source
    assert "just add_skill" in source
    assert "evals/" in source
    digest = hashlib.sha256(SKILL_MD.read_bytes()).hexdigest()
    assert digest in source


def test_skillui_does_not_instruct_unpinned_installs() -> None:
    skill_text = SKILL_MD.read_text()
    for needle in FORBIDDEN_INSTALL_SUBSTRINGS:
        assert needle not in skill_text, f"skill still instructs {needle!r}"
    match = UNPINNED_NPX_SKILLUI.search(skill_text)
    assert match is None, f"unpinned {match.group(0)!r}"
    assert CURL_PIPE_SH.search(skill_text) is None
    assert not _executable_install_hits(skill_text), _executable_install_hits(skill_text)
    assert "npm install -g" not in (REPO / "loadouts" / "uidesign.yaml").read_text()


def test_skillui_encodes_extract_modes_and_url_trust_boundary() -> None:
    text = SKILL_MD.read_text().lower()
    assert "--url" in text
    assert "--dir" in text
    assert "--repo" in text
    assert "http:" in text
    assert "https:" in text
    assert "skill.md" in text
    assert "design.md" in text
    assert "interactive" in text or "no flags" in text
    assert SKILLUI_VERSION in text


def test_skillui_treats_generated_skill_md_as_untrusted() -> None:
    text = SKILL_MD.read_text().lower()
    assert "untrusted" in text
    assert "~/.claude/skills" in text
    assert ".claude/skills" in text
    assert "~/.agents/skills" in text
    assert "do not invoke" in text
    assert "--no-skill" in text
    assert "single path segment" in text
    assert "design.md" in text
    assert "colors" in text
    assert "read the generated" not in text
    blob = json.dumps(json.loads((SKILL_ROOT / "evals" / "evals.json").read_text())).lower()
    assert "untrusted" in blob
    assert "~/.claude/skills" in blob
    assert "does not follow" in blob or "does not copy" in blob
    assert "design.md" in blob


def test_uidesign_sync_vendors_skillui_and_not_evals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    _silence_cli_tools(monkeypatch)
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [uidesign]
""",
    )

    sync(project)

    skill = project / ".claude" / "skills" / SKILL_NAME / "SKILL.md"
    assert skill.is_file()
    text = skill.read_text()
    assert f"name: {SKILL_NAME}" in text
    assert "--url" in text
    assert not list(project.rglob("evals"))
    assert (project / ".claude" / "skills" / SKILL_NAME / "SOURCE.md").is_file()


def test_base_sync_does_not_vendor_skillui(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [base]
""",
    )

    sync(project)

    assert not (project / ".claude" / "skills" / SKILL_NAME).exists()
