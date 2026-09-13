"""Contracts, scripts, and colocated evals for the make-readme skill."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

from loadout.frontmatter import parse_skill_md
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO / "skills" / "make-readme"
SKILL_MD = SKILL_ROOT / "SKILL.md"
SKILL_NAME = "make-readme"
INSPECT_SCRIPT = SKILL_ROOT / "scripts" / "inspect_repo.py"
SCORE_SCRIPT = SKILL_ROOT / "scripts" / "score_readme.py"
CORPUS_SCRIPT = SKILL_ROOT / "scripts" / "corpus_analyzer.py"
EVALS = SKILL_ROOT / "evals" / "evals.json"
WEAK_README = SKILL_ROOT / "evals" / "files" / "weak-readme.md"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _evals_payload() -> dict[str, object]:
    payload = json.loads(EVALS.read_text())
    assert isinstance(payload, dict)
    return payload


def test_make_readme_skill_parses() -> None:
    meta = parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name=SKILL_NAME)
    assert meta.name == SKILL_NAME
    assert meta.license == "MIT"
    lowered = meta.description.lower()
    assert lowered.startswith("use when")
    assert "readme" in lowered
    assert "/make-readme" in lowered


def test_github_loadout_ships_make_readme_skill() -> None:
    loadout = load_loadout(REPO / "loadouts" / "github.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert f"skills/{SKILL_NAME}" in srcs
    assert "skills/github-upload-media-to-pr" in srcs


def test_base_loadout_does_not_include_make_readme_skill() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert f"skills/{SKILL_NAME}" not in srcs


def test_body_requires_inspect_and_score_scripts() -> None:
    text = SKILL_MD.read_text()
    assert "scripts/inspect_repo.py" in text
    assert "scripts/score_readme.py" in text
    assert "scripts/corpus_analyzer.py" in text
    assert "README_TEMPLATE.md" in text
    assert "never invent facts" in text.lower()
    assert INSPECT_SCRIPT.is_file()
    assert SCORE_SCRIPT.is_file()
    assert CORPUS_SCRIPT.is_file()
    assert (SKILL_ROOT / "README_TEMPLATE.md").is_file()
    assert (SKILL_ROOT / "references" / "evidence.md").is_file()


def test_has_colocated_evals() -> None:
    payload = _evals_payload()
    assert payload["skill_name"] == SKILL_NAME
    evals = payload.get("evals")
    assert isinstance(evals, list) and evals
    for index, entry in enumerate(evals):
        assert isinstance(entry, dict)
        files = entry.get("files", [])
        if not isinstance(files, list):
            continue
        for relative in files:
            assert isinstance(relative, str)
            path = SKILL_ROOT / relative
            assert path.is_file(), f"{SKILL_NAME} evals[{index}] missing {relative}"


def test_evals_cover_create_improve_and_review_modes() -> None:
    payload = _evals_payload()
    evals = payload.get("evals")
    assert isinstance(evals, list)
    texts = []
    for entry in evals:
        assert isinstance(entry, dict)
        texts.append(
            "\n".join(
                [
                    str(entry.get("prompt", "")),
                    str(entry.get("expected_output", "")),
                    *(
                        [str(item) for item in entry["expectations"]]
                        if isinstance(entry.get("expectations"), list)
                        else []
                    ),
                ]
            ).lower()
        )
    blob = "\n".join(texts)
    assert "inspect_repo.py" in blob
    assert "score_readme.py" in blob
    assert "improve" in blob
    assert "review" in blob
    assert "does not invent" in blob or "instead of inventing" in blob
    assert "does not overwrite" in blob or "did not write readme.md" in blob


def test_inspect_repo_reports_gaps_from_disk(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo-lib"\nversion = "0.1.0"\ndescription = "A tiny demo library"\nrequires-python = ">=3.12"\n'
    )
    (tmp_path / "LICENSE").write_text("MIT License\n")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    facts = inspect.inspect(str(tmp_path))
    assert facts["name"] == "demo-lib"
    assert facts["license_guess"] == "MIT"
    assert "pypi" in facts["ecosystems"]
    assert any("No README" in gap for gap in facts["gaps"])


def test_score_readme_flags_placeholders_and_missing_install() -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    checks, stats = score.check(WEAK_README.read_text(), repo=str(SKILL_ROOT / "evals" / "files"))
    failed = {item["id"] for item in checks if not item["ok"]}
    assert "install" in failed
    assert "placeholders" in failed
    assert stats["lines"] > 0


def test_score_readme_cli_prints_score(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(WEAK_README.read_text())
    result = subprocess.run(
        [sys.executable, str(SCORE_SCRIPT), str(readme), "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert "score" in payload
    assert payload["score"] < 90


def test_github_sync_vendors_make_readme_without_evals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [github]\n")
    sync(project)
    dest = project / ".claude/skills" / SKILL_NAME
    assert (dest / "SKILL.md").is_file()
    assert (dest / "scripts" / "inspect_repo.py").is_file()
    assert (dest / "scripts" / "score_readme.py").is_file()
    assert (dest / "scripts" / "corpus_analyzer.py").is_file()
    assert (dest / "README_TEMPLATE.md").is_file()
    assert not (dest / "evals").exists()


def test_fetch_corpus_aborts_after_consecutive_github_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = _load_module(CORPUS_SCRIPT, "corpus_analyzer")
    ls_remote_calls = 0

    def fail_run(*args, **kwargs):
        nonlocal ls_remote_calls
        ls_remote_calls += 1
        raise subprocess.TimeoutExpired(cmd=["git"], timeout=30)

    def fail_urlopen(*args, **kwargs):
        raise urllib.error.URLError("mocked github failure")

    monkeypatch.setattr(corpus.subprocess, "run", fail_run)
    monkeypatch.setattr(corpus.urllib.request, "urlopen", fail_urlopen)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    corpus.fetch_corpus(str(tmp_path))

    assert ls_remote_calls <= 3
    assert ls_remote_calls > 0
    assert not any(tmp_path.iterdir())


def test_analyze_omits_stub_feature_keys(tmp_path: Path) -> None:
    corpus = _load_module(CORPUS_SCRIPT, "corpus_analyzer")
    readme = tmp_path / "README.md"
    readme.write_text("# Demo\n\nA short library description.\n")
    feats = corpus.analyze(str(readme))
    assert "license_shield_only" not in feats
    assert "first_code_line" not in feats
