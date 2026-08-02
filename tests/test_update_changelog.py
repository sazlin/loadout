import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "update_changelog.py"


def load_module():
    spec = importlib.util.spec_from_file_location("update_changelog", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


changelog = load_module()


def test_read_pyproject_version():
    text = '[project]\nname = "loadout"\nversion = "1.2.3"\n'
    assert changelog.read_pyproject_version(text) == "1.2.3"


def test_summarize_changes_filters_noise_and_dedupes():
    subjects = [
        "feat: add resolve --list",
        "fix(sync): preserve local overrides",
        "chore: bump deps",
        "ci: tweak workflow",
        "test: cover edge case",
        "docs: mention LOADOUT_PATH",
        "feat: add resolve --list",
        "Merge branch 'main' of origin",
        "Update changelog for 0.2.0",
    ]
    assert changelog.summarize_changes(subjects) == [
        "Add resolve --list",
        "Preserve local overrides",
    ]


def test_insert_changelog_entry_newest_first():
    existing = "# CHANGELOG\n\n## 0.1.0\n\n- Initial release\n"
    updated = changelog.insert_changelog_entry(
        existing,
        "0.2.0",
        ["Add resolve --list", "Fix sync drift checks"],
    )
    assert updated.startswith("# CHANGELOG\n\n## 0.2.0\n")
    assert "- Add resolve --list\n" in updated
    assert "- Fix sync drift checks\n" in updated
    assert updated.index("## 0.2.0") < updated.index("## 0.1.0")


def test_insert_changelog_entry_is_idempotent():
    existing = "# CHANGELOG\n\n## 0.2.0\n\n- Already there\n\n## 0.1.0\n\n- Initial\n"
    updated = changelog.insert_changelog_entry(existing, "0.2.0", ["Ignored"])
    assert updated == existing


def test_changelog_has_version():
    text = "# CHANGELOG\n\n## 0.1.0\n\n- Initial\n"
    assert changelog.changelog_has_version(text, "0.1.0")
    assert not changelog.changelog_has_version(text, "0.2.0")
