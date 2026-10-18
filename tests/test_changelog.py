"""Contracts for published CHANGELOG slices `loadout update` prints."""

from pathlib import Path

from loadout.update import _slice_sections

REPO = Path(__file__).resolve().parent.parent


def test_v0_15_0_slice_from_v0_14_0_includes_playwright_cli() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.14.0", "v0.15.0")

    assert "playwright-cli" in notes
    assert "## 0.13.0" not in notes


def test_v0_17_0_slice_from_v0_16_0_includes_release_notes() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.16.0", "v0.17.0")

    assert "stripe" in notes
    assert "pr_review_harness" in notes
    assert "playwright-e2e" in notes
    assert "## 0.16.0" not in notes


def test_slice_from_v0_50_0_to_v0_51_0_is_only_0_51_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.50.0", "v0.51.0")

    assert notes.strip() == "## 0.51.0"
    assert "## 0.49.0" not in notes
    assert "## 0.50.0" not in notes


def test_slice_from_v0_52_0_to_v0_53_0_is_only_0_53_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.52.0", "v0.53.0")

    assert notes.strip() == "## 0.53.0"
    assert "## 0.49.0" not in notes
    assert "## 0.50.0" not in notes
    assert "## 0.51.0" not in notes
    assert "## 0.52.0" not in notes


def test_slice_from_v0_53_0_to_v0_54_0_includes_tailscale() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.53.0", "v0.54.0")

    assert "tailscale" in notes
    assert "## 0.53.0" not in notes


def test_slice_from_v0_54_0_to_v0_55_0_includes_migration_runner() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.54.0", "v0.55.0")

    assert "migration-runner" in notes
    assert "db-migrations" in notes
    assert "## 0.54.0" not in notes


def test_slice_from_v0_55_0_to_v0_56_0_is_only_0_56_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.55.0", "v0.56.0")

    assert notes.strip() == "## 0.56.0"
    assert "## 0.54.0" not in notes
    assert "## 0.55.0" not in notes


def test_slice_from_v0_56_0_to_v0_57_0_includes_release_notes() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.56.0", "v0.57.0")

    assert "repo-conventions" in notes
    assert "orca-native-worktree" in notes
    assert "## 0.56.0" not in notes


def test_slice_from_v0_57_0_to_v0_58_0_is_only_0_58_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.57.0", "v0.58.0")

    assert notes.strip() == "## 0.58.0"
    assert "## 0.55.0" not in notes
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes


def test_slice_from_v0_58_0_to_v0_59_0_is_only_0_59_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.58.0", "v0.59.0")

    assert notes.strip() == "## 0.59.0"
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes
    assert "## 0.58.0" not in notes


def test_slice_from_v0_59_0_to_v0_60_0_is_only_0_60_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.59.0", "v0.60.0")

    assert notes.strip() == "## 0.60.0"
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes
    assert "## 0.58.0" not in notes
    assert "## 0.59.0" not in notes


def test_slice_from_v0_60_0_to_v0_61_0_is_only_0_61_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.60.0", "v0.61.0")

    assert notes.strip() == "## 0.61.0"
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes
    assert "## 0.58.0" not in notes
    assert "## 0.59.0" not in notes
    assert "## 0.60.0" not in notes


def test_slice_from_v0_61_0_to_v0_62_0_is_only_0_62_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.61.0", "v0.62.0")

    assert notes.strip() == "## 0.62.0"
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes
    assert "## 0.58.0" not in notes
    assert "## 0.59.0" not in notes
    assert "## 0.60.0" not in notes
    assert "## 0.61.0" not in notes


def test_slice_from_v0_62_0_to_v0_63_0_is_only_0_63_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.62.0", "v0.63.0")

    assert notes.strip() == "## 0.63.0"
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes
    assert "## 0.58.0" not in notes
    assert "## 0.59.0" not in notes
    assert "## 0.60.0" not in notes
    assert "## 0.61.0" not in notes
    assert "## 0.62.0" not in notes


def test_slice_from_v0_63_0_to_v0_64_0_is_only_0_64_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.63.0", "v0.64.0")

    assert notes.strip() == "## 0.64.0"
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes
    assert "## 0.58.0" not in notes
    assert "## 0.59.0" not in notes
    assert "## 0.60.0" not in notes
    assert "## 0.61.0" not in notes
    assert "## 0.62.0" not in notes
    assert "## 0.63.0" not in notes


def test_slice_from_v0_64_0_to_v0_65_0_is_only_0_65_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.64.0", "v0.65.0")

    assert notes.strip() == "## 0.65.0"
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes
    assert "## 0.58.0" not in notes
    assert "## 0.59.0" not in notes
    assert "## 0.60.0" not in notes
    assert "## 0.61.0" not in notes
    assert "## 0.62.0" not in notes
    assert "## 0.63.0" not in notes
    assert "## 0.64.0" not in notes


def test_slice_from_v0_65_0_to_v0_66_0_is_only_0_66_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.65.0", "v0.66.0")

    assert notes.strip() == "## 0.66.0"
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes
    assert "## 0.58.0" not in notes
    assert "## 0.59.0" not in notes
    assert "## 0.60.0" not in notes
    assert "## 0.61.0" not in notes
    assert "## 0.62.0" not in notes
    assert "## 0.63.0" not in notes
    assert "## 0.64.0" not in notes
    assert "## 0.65.0" not in notes


def test_slice_from_v0_66_0_to_v0_67_0_is_only_0_67_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.66.0", "v0.67.0")

    assert notes.strip() == "## 0.67.0"
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes
    assert "## 0.58.0" not in notes
    assert "## 0.59.0" not in notes
    assert "## 0.60.0" not in notes
    assert "## 0.61.0" not in notes
    assert "## 0.62.0" not in notes
    assert "## 0.63.0" not in notes
    assert "## 0.64.0" not in notes
    assert "## 0.65.0" not in notes
    assert "## 0.66.0" not in notes


def test_slice_from_v0_67_0_to_v0_68_0_is_only_0_68_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.67.0", "v0.68.0")

    assert notes.strip() == "## 0.68.0"
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes
    assert "## 0.58.0" not in notes
    assert "## 0.59.0" not in notes
    assert "## 0.60.0" not in notes
    assert "## 0.61.0" not in notes
    assert "## 0.62.0" not in notes
    assert "## 0.63.0" not in notes
    assert "## 0.64.0" not in notes
    assert "## 0.65.0" not in notes
    assert "## 0.66.0" not in notes
    assert "## 0.67.0" not in notes


def test_slice_from_v0_68_0_to_v0_69_0_is_only_0_69_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.68.0", "v0.69.0")

    assert notes.strip() == "## 0.69.0"
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes
    assert "## 0.58.0" not in notes
    assert "## 0.59.0" not in notes
    assert "## 0.60.0" not in notes
    assert "## 0.61.0" not in notes
    assert "## 0.62.0" not in notes
    assert "## 0.63.0" not in notes
    assert "## 0.64.0" not in notes
    assert "## 0.65.0" not in notes
    assert "## 0.66.0" not in notes
    assert "## 0.67.0" not in notes
    assert "## 0.68.0" not in notes


def test_slice_from_v0_69_0_to_v0_70_0_is_only_0_70_0() -> None:
    changelog = (REPO / "CHANGELOG.md").read_text()
    notes = _slice_sections(changelog, "v0.69.0", "v0.70.0")

    assert notes.strip() == "## 0.70.0"
    assert "## 0.56.0" not in notes
    assert "## 0.57.0" not in notes
    assert "## 0.58.0" not in notes
    assert "## 0.59.0" not in notes
    assert "## 0.60.0" not in notes
    assert "## 0.61.0" not in notes
    assert "## 0.62.0" not in notes
    assert "## 0.63.0" not in notes
    assert "## 0.64.0" not in notes
    assert "## 0.65.0" not in notes
    assert "## 0.66.0" not in notes
    assert "## 0.67.0" not in notes
    assert "## 0.68.0" not in notes
    assert "## 0.69.0" not in notes
