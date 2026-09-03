"""Contracts for the stripe loadout and vendored Stripe agent skills."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from loadout.models import load_loadout

REPO = Path(__file__).resolve().parent.parent
SKILL_NAMES = (
    "connect-recommend",
    "connect-required-verification-information",
    "stripe-apps",
    "stripe-best-practices",
    "stripe-directory",
    "stripe-docs",
    "stripe-projects",
    "upgrade-stripe",
)
SKILL_SRCS = tuple(f"skills/{name}" for name in SKILL_NAMES)


def write_manifest(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / ".loadout.yaml").write_text(body)


def test_stripe_loadout_ships_vendored_stripe_skills() -> None:
    loadout = load_loadout(REPO / "loadouts" / "stripe.yaml")
    assert loadout.name == "stripe"
    assert loadout.extends == []
    assert {entry["src"] for entry in loadout.skills} == set(SKILL_SRCS)
    assert loadout.rules == []
    assert loadout.agents == []
    assert loadout.mcps == []


def test_stripe_skill_evals_are_colocated() -> None:
    for name, src in zip(SKILL_NAMES, SKILL_SRCS, strict=True):
        evals = REPO / src / "evals" / "evals.json"
        payload = json.loads(evals.read_text())
        assert payload["skill_name"] == name
        assert payload["evals"]
        for index, entry in enumerate(payload["evals"]):
            for relative in entry.get("files", []):
                path = REPO / src / relative
                assert path.is_file(), f"{name} evals[{index}] missing {relative}"


# Upstream SKILL.md needles: prose install lines plus Cursor `Bash(...)`
# allowed-tools grants that SOURCE.md says to strip on bump (not typos).
FORBIDDEN_INSTALL_SUBSTRINGS = (
    "npm i -g @stripe/cli",
    "npx skills add https://github.com/stripe/ai",
    "Bash(brew install stripe/stripe-cli/stripe)",
    "Bash(npx skills add https://docs.stripe.com *)",
)
# Tree-wide command phrases with refusal exemptions; not a replacement for
# FORBIDDEN_INSTALL_SUBSTRINGS (SKILL.md-only, no exemptions, exact grant strings).
EXECUTABLE_INSTALL_NEEDLES = (
    "stripe plugin install",
    "brew install",
    "npm i -g",
    "npx skills add",
    "curl | sh",
)
_SKILL_TEXT_SUFFIXES = {".md", ".txt", ".yaml", ".yml"}
_REFUSAL_MARKERS = ("do not run", "does not run", "does not auto-run", "do not execute")
IMPORTED_SKILL_HASH_LABEL = "Imported SKILL.md sha256"
CURRENT_SKILL_HASH_LABEL = "Current SKILL.md sha256"
UNLABELED_SKILL_HASH_ROW = "| SKILL.md sha256 |"


def _iter_skill_text_files(skill_src: Path) -> list[Path]:
    files: list[Path] = []
    for path in skill_src.rglob("*"):
        if not path.is_file():
            continue
        if "evals" in path.relative_to(skill_src).parts:
            continue
        if path.suffix.lower() not in _SKILL_TEXT_SUFFIXES:
            continue
        files.append(path)
    return files


def _install_phrase_is_refusal(previous: str, line: str) -> bool:
    """True skips a Do-not-run mention unless the window is gated and also contains an EXECUTABLE_INSTALL_NEEDLES phrase."""
    window = " ".join(f"{previous} {line}".split()).lower()
    if not any(marker in window for marker in _REFUSAL_MARKERS):
        return False
    gated = (
        "without approval" in window
        or "without explicit user approval" in window
        or "until they confirm" in window
        or "until they agree" in window
    )
    has_install_command = any(needle in window for needle in EXECUTABLE_INSTALL_NEEDLES)
    return not (gated and has_install_command)


def _executable_install_hits(text: str) -> list[str]:
    hits: list[str] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        previous = lines[index - 1] if index else ""
        if _install_phrase_is_refusal(previous, line):
            continue
        for needle in EXECUTABLE_INSTALL_NEEDLES:
            if needle in line:
                hits.append(f"{needle!r} in {line.strip()!r}")
    return hits


def test_executable_install_hits_treats_refusals_as_non_hits() -> None:
    assert _executable_install_hits("stripe plugin install apps\n")
    assert not _executable_install_hits("Do not run `brew install`, `npm i -g`, `npx skills add`, or `curl | sh`.\n")
    gated = (
        "tell the user to install the Projects plugin themselves "
        "(`stripe plugin install projects`). Do not run plugin install "
        "without explicit user approval.\n"
    )
    assert _executable_install_hits(gated)
    assert not _executable_install_hits("Do not run `stripe plugin install`.\n")
    assert not _executable_install_hits("does not run `stripe plugin install`.\n")
    assert not _executable_install_hits("Do not run `npx skills add`.\n")


def test_stripe_skills_do_not_instruct_unpinned_installs() -> None:
    for src in SKILL_SRCS:
        skill_root = REPO / src
        skill_md = (skill_root / "SKILL.md").read_text()
        for needle in FORBIDDEN_INSTALL_SUBSTRINGS:
            assert needle not in skill_md, f"{src} still instructs {needle!r}"
        for path in _iter_skill_text_files(skill_root):
            hits = _executable_install_hits(path.read_text())
            assert not hits, f"{path.relative_to(REPO)} still instructs {hits}"


def test_stripe_projects_does_not_handoff_to_generated_skill() -> None:
    text = (REPO / "skills" / "stripe-projects" / "SKILL.md").read_text().lower()
    assert "do not invoke" in text
    assert "stripe-projects-cli" in text
    assert "skill tool with name `stripe-projects-cli`" not in text
    assert "--accept-tos --yes" not in text


def _assert_adapted_source_hash_label(src: str, text: str) -> None:
    if "**Adapted**" not in text:
        return
    has_imported = f"| {IMPORTED_SKILL_HASH_LABEL} |" in text
    has_current = f"| {CURRENT_SKILL_HASH_LABEL} |" in text
    assert has_imported or has_current, f"{src} adapted SOURCE.md must label the SKILL.md hash as Imported or Current"
    assert UNLABELED_SKILL_HASH_ROW not in text, f"{src} adapted SOURCE.md still has unlabeled SKILL.md sha256"
    if has_current:
        digest = hashlib.sha256((REPO / src / "SKILL.md").read_bytes()).hexdigest()
        assert digest in text, f"{src} Current SKILL.md sha256 does not match SKILL.md"
    _assert_no_remaining_verbatim_leftover(src, text)


def _assert_no_remaining_verbatim_leftover(src: str, text: str) -> None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        chunk = line
        if index + 1 < len(lines) and lines[index + 1].startswith("   "):
            chunk = f"{line} {lines[index + 1]}"
        if "Upstream-verbatim" in chunk:
            assert "remaining" not in chunk.lower(), f"{src} Upstream-verbatim leftover names remaining copy: {chunk}"


def test_stripe_skill_source_pins_exist() -> None:
    for src in SKILL_SRCS:
        source = REPO / src / "SOURCE.md"
        text = source.read_text()
        assert "docs.stripe.com/.well-known/skills/index.json" in text
        assert "just add_skill" in text
        assert "evals/" in text
        _assert_adapted_source_hash_label(src, text)
        if "**Adapted**" in text and "references/workflow.md" in text:
            bump_prose = text.split("## Adaptations from upstream", 1)[0]
            assert "workflow.md" in bump_prose, (
                f"{src} Adapted references/workflow.md but bump/import prose does not name it"
            )
        if src == "skills/stripe-projects" and "**Adapted**" in text:
            adaptations = text.split("## Adaptations from upstream", 1)[1]
            assert "docs.stripe.com/stripe-cli" in adaptations
