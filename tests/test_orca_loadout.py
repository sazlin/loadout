"""Contracts for the orca loadout and vendored Orca discovery stubs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
SKILL_NAMES = (
    "orca-cli",
    "orchestration",
    "computer-use",
    "orca-linear",
    "orca-emulator",
    "orca-emulator-android",
    "orca-per-workspace-env",
)
UPSTREAM_COMMIT = "24b97e89090a0aa8ec28a9a44bf5ea6248965a97"


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def test_orca_loadout_ships_vendored_orca_skills() -> None:
    loadout = load_loadout(REPO / "loadouts" / "orca.yaml")
    assert loadout.name == "orca"
    assert loadout.extends == []
    assert [entry["src"] for entry in loadout.skills] == [f"skills/{name}" for name in SKILL_NAMES]
    assert loadout.rules == []
    assert loadout.agents == []
    assert loadout.mcps == []


def test_orca_skill_pins_match_skill_md() -> None:
    for name in SKILL_NAMES:
        root = REPO / "skills" / name
        skill_md = (root / "SKILL.md").read_text()
        source = (root / "SOURCE.md").read_text()
        digest = hashlib.sha256((root / "SKILL.md").read_bytes()).hexdigest()
        assert f"name: {name}" in skill_md
        assert f"skills get {name}" in skill_md
        assert UPSTREAM_COMMIT in source
        assert digest in source
        assert f"skills/{name}" in source


def test_orca_skill_evals_are_colocated() -> None:
    for name in SKILL_NAMES:
        evals = REPO / "skills" / name / "evals" / "evals.json"
        payload = json.loads(evals.read_text())
        assert payload["skill_name"] == name
        assert payload["evals"]
        for index, entry in enumerate(payload["evals"]):
            joined = " ".join(entry["expectations"])
            assert f"skills get {name}" in joined
            assert "follows that guide" not in joined
            for relative in entry.get("files", []):
                path = REPO / "skills" / name / relative
                assert path.is_file(), f"{name} evals[{index}] missing {relative}"


def _compact(text: str) -> str:
    return " ".join(text.lower().split())


def test_orca_skills_do_not_escalate_on_runtime_access_denied() -> None:
    for name in SKILL_NAMES:
        text = (REPO / "skills" / name / "SKILL.md").read_text()
        assert "re-run it with escalated permissions" not in text
        assert "runtime_access_denied" in text
        denied = _compact(text.split("runtime_access_denied", 1)[1][:500])
        assert "stop" in denied
        assert "ask the human" in denied
        source = (REPO / "skills" / name / "SOURCE.md").read_text()
        assert "**Adapted**" in source
        assert "runtime_access_denied" in source


def test_orca_skills_do_not_treat_env_or_skills_get_as_policy() -> None:
    for name in SKILL_NAMES:
        text = (REPO / "skills" / name / "SKILL.md").read_text()
        compact = _compact(text)
        assert "ORCA_CLI_COMMAND" in text
        assert "use its value" not in text
        assert "existing executable path" in compact
        assert "shell metacharacters" in compact
        assert "untrusted" in compact
        assert "binding operational policy" in compact
        assert "Load the version-matched guide before running Orca commands" not in text
        source = (REPO / "skills" / name / "SOURCE.md").read_text()
        assert "ORCA_CLI_COMMAND" in source
        assert "skills get" in source


def test_orca_sync_vendors_skills_and_not_evals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    write_manifest(
        project,
        """source: https://github.com/sazlin/loadout
ref: main
loadouts: [orca]
""",
    )

    sync(project)

    for name in SKILL_NAMES:
        skill = project / ".claude" / "skills" / name / "SKILL.md"
        assert skill.is_file()
        assert f"skills get {name}" in skill.read_text()
        assert (project / ".claude" / "skills" / name / "SOURCE.md").is_file()
    assert not list(project.rglob("evals"))


def test_base_sync_does_not_vendor_orca_skills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    assert not (project / ".claude" / "skills" / "orca-cli").exists()
