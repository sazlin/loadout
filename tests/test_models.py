from pathlib import Path

import pytest

from loadout.errors import ValidationError
from loadout.models import load_lockfile, load_manifest


def test_load_manifest_defaults(tmp_path: Path):
    p = tmp_path / ".loadout.yaml"
    p.write_text(
        "source: https://github.com/sazlin/loadout\n"
        "ref: v0.1.0\n"
        "loadouts:\n  - base\n"
    )
    m = load_manifest(p)
    assert m.skills_dir == ".claude/skills"
    assert m.claude_bridge is True
    assert m.include == []
    assert m.exclude == []


def test_load_manifest_rejects_malformed_yaml(tmp_path: Path):
    path = tmp_path / ".loadout.yaml"
    path.write_text("source: https://example.com/loadout\nloadouts: [\n")

    with pytest.raises(ValidationError, match=r"\.loadout\.yaml: invalid YAML"):
        load_manifest(path)


def test_load_lockfile_rejects_malformed_json(tmp_path: Path):
    path = tmp_path / ".loadout.lock"
    path.write_text('{"lockfile_version": 1,\n')

    with pytest.raises(ValidationError, match=r"\.loadout\.lock: invalid JSON"):
        load_lockfile(path)
