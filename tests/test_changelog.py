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
