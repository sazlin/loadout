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
