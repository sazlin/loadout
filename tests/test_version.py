import tomllib
from pathlib import Path

from loadout import __version__

REPO = Path(__file__).resolve().parent.parent
RELEASE = "0.50.0"


def test_version_is_semver():
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_version_is_0_50_0():
    assert __version__ == RELEASE


def test_changelog_has_0_50_0_heading():
    headings = [line for line in (REPO / "CHANGELOG.md").read_text().splitlines() if line.startswith("## ")]
    assert f"## {RELEASE}" in headings


# One-off for the empty 0.50.0 cut; delete this test on the next release that has notes instead of renaming it with RELEASE.
def test_0_50_0_changelog_section_is_empty():
    changelog = (REPO / "CHANGELOG.md").read_text().splitlines()
    start = changelog.index("## 0.50.0")
    end = next(i for i, line in enumerate(changelog[start + 1 :], start + 1) if line.startswith("## "))
    section = [line for line in changelog[start + 1 : end] if line.strip()]
    assert section == []


def test_pyproject_version_is_0_50_0():
    data = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert data["project"]["version"] == RELEASE


def test_uv_lock_loadout_version_is_0_50_0():
    packages = tomllib.loads((REPO / "uv.lock").read_text())["package"]
    loadout = next(pkg for pkg in packages if pkg["name"] == "loadout")
    assert loadout["version"] == RELEASE
