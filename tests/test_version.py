from loadout import __version__


def test_version_is_semver():
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_version_is_0_36_0():
    assert __version__ == "0.36.0"
