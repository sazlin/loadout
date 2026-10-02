"""Contracts for the vendored tailscale skill on the base loadout."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from loadout.frontmatter import parse_skill_md
from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO / "skills" / "tailscale"
SKILL_MD = SKILL_ROOT / "SKILL.md"
PINNED_SHA256 = "64599f6420ce68bfebf246ecb1bcb6aadcd1bf4aaacce706a8709c6a97c3e1f6"
PINNED_COMMIT = "4f05d353efc56962546aa26ccc59bb08ca699ad1"


def test_tailscale_skill_parses() -> None:
    assert SKILL_MD.is_file(), SKILL_MD
    meta = parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name="tailscale")
    assert meta.name == "tailscale"
    assert "Tailscale" in meta.description


def test_base_loadout_includes_tailscale() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert "skills/tailscale" in srcs


def test_tailscale_source_pin_matches_skill_bytes() -> None:
    source = (SKILL_ROOT / "SOURCE.md").read_text()
    digest = hashlib.sha256(SKILL_MD.read_bytes()).hexdigest()
    assert digest == PINNED_SHA256
    assert PINNED_SHA256 in source
    assert PINNED_COMMIT in source
    assert "tailscale/tailscale-skill" in source
    assert "curl | sh" in source


def test_tailscale_how_references_names_each_file_once() -> None:
    skill = SKILL_MD.read_text()
    start = skill.index("## How references work")
    end = skill.index("## Core concepts")
    section = skill[start:end]
    remaining = next(line for line in section.splitlines() if "self-contained" in line)
    descriptive = next(line for line in section.splitlines() if "Descriptive references" in line)
    names = sorted(path.name for path in (SKILL_ROOT / "references").glob("*.md"))
    for name in names:
        assert section.count(f"`{name}`") == 1, name
        text = (SKILL_ROOT / "references" / name).read_text()
        if "WebFetch" in text:
            assert name not in remaining, name
        if f"`{name}`" in descriptive:
            assert "WebFetch" in text, name


def test_tailscale_body_refuses_unpinned_install() -> None:
    text = SKILL_MD.read_text()
    assert "curl -fsSL https://tailscale.com/install.sh | sh" not in text
    assert "do not pipe a remote script into a shell" in text.lower()
    assert "http://tailscale.com" not in text
    assert "https://tailscale.com/download" in text
    install = (SKILL_ROOT / "references" / "installation.md").read_text()
    assert "curl -fsSL https://tailscale.com/install.sh | sh" not in install
    assert "http://tailscale.com" not in install
    assert "http://" not in install
    linux, _, rest = install.partition("## macOS")
    arch_at = linux.index("### Arch Linux")
    mainstream = linux[:arch_at]
    arch = linux[arch_at:]
    assert "Ubuntu" in mainstream and "Debian" in mainstream and "RHEL" in mainstream
    assert "apt install tailscale" not in mainstream
    assert "dnf install tailscale" not in mainstream
    assert "yum install tailscale" not in mainstream
    assert "https://tailscale.com/download" in mainstream
    assert "https://pkgs.tailscale.com/stable/" in mainstream
    assert "pacman" in arch
    assert "NixOS" in arch
    quick_start = text.split("## Quick start", 1)[1].split("## Find your task", 1)[0]
    assert "from the distro package (`apt`, `dnf`, or `yum`)" not in quick_start
    assert "https://tailscale.com/download" in rest
    containers = (SKILL_ROOT / "references" / "containers.md").read_text()
    assert "tailscale/tailscale:latest" not in containers
    assert "--version <chart-version>" in containers


def test_tailscale_session_recording_pin() -> None:
    recording = (SKILL_ROOT / "references" / "session-recording.md").read_text()
    assert "tsrecorder:<version>@sha256:<digest>" in recording
    assert "AWS_ACCESS_KEY_ID" in recording
    assert "AWS_SECRET_ACCESS_KEY" in recording
    assert "-e AWS_ACCESS_KEY_ID" not in recording
    assert "-e AWS_SECRET_ACCESS_KEY" not in recording
    assert "do not pass cloud credentials into this container" in recording.lower()


def test_tailscale_tsnet_pin() -> None:
    tsnet = (SKILL_ROOT / "references" / "tsnet.md").read_text()
    assert "go get tailscale.com/tsnet@<released-version>" in tsnet
    assert "Do not run `go get tailscale.com/tsnet` without `@<released-version>`." in tsnet


def test_tailscale_github_action_pin() -> None:
    enterprise = (SKILL_ROOT / "references" / "enterprise.md").read_text()
    assert "tailscale/github-action@<full-commit-sha>" in enterprise
    assert "Do not use a floating ref such as `@v4`" in enterprise


def test_tailscale_serve_identity_headers_require_proxy_trust() -> None:
    sharing = (SKILL_ROOT / "references" / "sharing-and-publishing.md").read_text()
    login = sharing.index("Tailscale-User-Login")
    header_note = sharing[max(0, login - 400) : login + 700]
    assert "without any extra setup" not in header_note
    assert "loopback" in header_note
    assert "Funnel" in header_note
    assert "do not use these headers as authentication" in header_note.lower()
    tsnet = (SKILL_ROOT / "references" / "tsnet.md").read_text()
    assert (
        "trust them only when the immediate `RemoteAddr` is loopback, "
        "and still look up capabilities via `WhoIs`"
        in tsnet
    )


def test_tailscale_evals_are_colocated() -> None:
    evals = SKILL_ROOT / "evals" / "evals.json"
    payload = json.loads(evals.read_text())
    assert payload["skill_name"] == "tailscale"
    prompts = [entry["prompt"] for entry in payload["evals"]]
    assert any("Install Tailscale" in prompt for prompt in prompts)
    assert any("AWS keys" in prompt for prompt in prompts)
