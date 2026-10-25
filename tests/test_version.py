import tomllib
from pathlib import Path

from loadout import __version__

REPO = Path(__file__).resolve().parent.parent
RELEASE = "0.77.0"


def test_version_is_semver():
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_version_is_0_77_0():
    assert __version__ == RELEASE


def test_changelog_has_0_77_0_heading():
    headings = [line for line in (REPO / "CHANGELOG.md").read_text().splitlines() if line.startswith("## ")]
    assert f"## {RELEASE}" in headings


def test_changelog_keeps_0_76_0_heading():
    headings = [line for line in (REPO / "CHANGELOG.md").read_text().splitlines() if line.startswith("## ")]
    assert headings.index("## 0.77.0") < headings.index("## 0.76.0") < headings.index("## 0.75.0")


def test_pyproject_version_is_0_77_0():
    data = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert data["project"]["version"] == RELEASE


def test_uv_lock_loadout_version_is_0_77_0():
    packages = tomllib.loads((REPO / "uv.lock").read_text())["package"]
    loadout = next(pkg for pkg in packages if pkg["name"] == "loadout")
    assert loadout["version"] == RELEASE
