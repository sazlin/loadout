from pathlib import Path

from loadout.models import load_manifest


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
