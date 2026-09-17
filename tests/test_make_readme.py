"""Contracts, scripts, and colocated evals for the make-readme skill."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import urllib.error
from pathlib import Path
from types import ModuleType

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
CLI_WEAK_README = SKILL_ROOT / "evals" / "files" / "cli-weak-readme.md"
FEATURES_GUIDES = (
    SKILL_MD,
    SKILL_ROOT / "README_TEMPLATE.md",
    SKILL_ROOT / "references" / "section-playbook.md",
)


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _evals_payload() -> dict[str, object]:
    payload = json.loads(EVALS.read_text())
    assert isinstance(payload, dict)
    return payload


def _eval_texts(payload: dict[str, object]) -> str:
    raw = payload.get("evals")
    if not isinstance(raw, list):
        return ""
    chunks: list[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        chunks.append(str(entry.get("prompt", "")))
        chunks.append(str(entry.get("expected_output", "")))
        expectations = entry.get("expectations")
        if isinstance(expectations, list):
            chunks.extend(str(item) for item in expectations)
    return "\n".join(chunks).lower()


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


def test_body_requires_scripts_template_and_evidence() -> None:
    text = SKILL_MD.read_text()
    assert "scripts/inspect_repo.py" in text
    assert "scripts/score_readme.py" in text
    assert "scripts/corpus_analyzer.py" in text
    assert "README_TEMPLATE.md" in text
    assert INSPECT_SCRIPT.is_file()
    assert SCORE_SCRIPT.is_file()
    assert CORPUS_SCRIPT.is_file()
    assert (SKILL_ROOT / "README_TEMPLATE.md").is_file()
    assert (SKILL_ROOT / "references" / "evidence.md").is_file()


def test_body_requires_never_invent_facts() -> None:
    text = SKILL_MD.read_text()
    assert "never invent facts" in text.lower()


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
    blob = _eval_texts(_evals_payload())
    assert "inspect_repo.py" in blob
    assert "score_readme.py" in blob
    assert "improve" in blob
    assert "review" in blob
    assert "does not invent" in blob or "instead of inventing" in blob
    assert "does not overwrite" in blob or "did not write readme.md" in blob
    assert "commented command catalog" in blob
    assert "git slug" in blob
    assert "without x" in blob
    assert "8 invocations" in blob


def test_body_requires_cli_catalog_rules() -> None:
    text = SKILL_MD.read_text().lower()
    assert "comment" in text and "--help" in text
    assert "git slug" in text or "git folder" in text
    assert "without x" in text
    assert "differentiat" in text
    assert "at most 8 invocations" in text


def test_features_sell_the_experience_not_implementation_trivia() -> None:
    slogan = "sell the experience in terms the target user will appreciate"
    for path in FEATURES_GUIDES:
        text = path.read_text().lower()
        assert slogan in text, path.name
        assert "sell the switch" not in text, path.name
        assert "switch reason" not in text, path.name
        assert "why would i switch" not in text, path.name
        assert "share the same argv" in text, path.name

    template = (SKILL_ROOT / "README_TEMPLATE.md").read_text()
    playbook = (SKILL_ROOT / "references" / "section-playbook.md").read_text()
    for text in (template, playbook):
        assert "**Tight guest mounts.**" in text
        assert "**Secure guest mounts.**" in text
        assert "`ro,noexec`" in text

    features_section = playbook.lower().split("## 5. features")[1].split("## 6.")[0]
    assert "**failure modes:**" in features_section
    assert "share the same argv" in features_section
    assert "tight guest mounts" in features_section


def test_cli_eval_rejects_argv_trivia_and_mechanism_named_benefits() -> None:
    payload = _evals_payload()
    evals = payload["evals"]
    assert isinstance(evals, list)
    eval4 = next(entry for entry in evals if isinstance(entry, dict) and entry.get("id") == 4)
    blob = "\n".join(
        [str(eval4.get("expected_output", ""))] + [str(item) for item in eval4.get("expectations", [])]
    ).lower()
    assert "argv" in blob
    assert "tight guest mounts" in blob
    fixture = CLI_WEAK_README.read_text()
    assert "**Tight guest mounts.**" in fixture
    assert "share the same argv" in fixture


def test_template_has_cli_and_library_quick_start_fillins() -> None:
    template = (SKILL_ROOT / "README_TEMPLATE.md").read_text()
    assert "{{BINARY}} --help" in template
    assert "{{HERO_COMMAND}}" in template
    assert "```bash" in template
    assert "{{LANGUAGE_TAG}}" in template
    assert "{{MINIMAL_RUNNABLE_EXAMPLE}}" in template
    assert "{{EXPECTED_OUTPUT}}" in template
    assert "```{{LANGUAGE_TAG}}" in template
    assert "delete the unused" in template.lower()


def test_cli_catalog_cap_is_eight_plus_help() -> None:
    for path in (
        SKILL_ROOT / "README_TEMPLATE.md",
        SKILL_MD,
        SKILL_ROOT / "references" / "section-playbook.md",
    ):
        text = path.read_text().lower()
        assert "at most 8 invocations" in text, path.name
        assert "details" in text


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


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
    assert isinstance(facts["demo_media"], list)
    assert "has_demo_media" not in facts


def test_inspect_repo_keeps_dotted_github_repo_slug(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    https_repo = tmp_path / "https"
    ssh_repo = tmp_path / "ssh"
    https_repo.mkdir()
    ssh_repo.mkdir()
    _git(https_repo, "init")
    _git(https_repo, "remote", "add", "origin", "https://github.com/vercel/next.js.git")
    https_facts = inspect.inspect(str(https_repo))
    assert https_facts["owner"] == "vercel"
    assert https_facts["repo"] == "next.js"

    _git(ssh_repo, "init")
    _git(ssh_repo, "remote", "add", "origin", "git@github.com:foo/bar.git")
    ssh_facts = inspect.inspect(str(ssh_repo))
    assert ssh_facts["owner"] == "foo"
    assert ssh_facts["repo"] == "bar"


def test_inspect_repo_default_branch_follows_origin_head(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    repo = tmp_path / "with-origin"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "dev@example.com")
    _git(repo, "config", "user.name", "Dev")
    _git(repo, "commit", "--allow-empty", "-m", "init")
    _git(repo, "checkout", "-b", "feat/foo")
    _git(repo, "remote", "add", "origin", "https://github.com/example/demo.git")
    _git(repo, "update-ref", "refs/remotes/origin/main", "main")
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    facts = inspect.inspect(str(repo))
    assert facts["default_branch"] == "main"

    lonely = tmp_path / "no-remotes"
    lonely.mkdir()
    _git(lonely, "init", "-b", "main")
    lonely_facts = inspect.inspect(str(lonely))
    assert lonely_facts["default_branch"] == "main"


def test_inspect_repo_skips_npm_install_when_package_json_invalid_or_unnamed(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "package.json").write_text("{")
    broken_facts = inspect.inspect(str(broken))
    assert "npm" not in broken_facts["ecosystems"]
    assert broken_facts["suggested_install_commands"] == []
    assert "None" not in " ".join(broken_facts["suggested_install_commands"])

    unnamed = tmp_path / "unnamed"
    unnamed.mkdir()
    (unnamed / "package.json").write_text("{}")
    unnamed_facts = inspect.inspect(str(unnamed))
    assert not any("npm install" in cmd for cmd in unnamed_facts["suggested_install_commands"])
    assert "None" not in " ".join(unnamed_facts["suggested_install_commands"])

    named = tmp_path / "named"
    named.mkdir()
    (named / "package.json").write_text(json.dumps({"name": "demo-cli", "bin": {"demo": "cli.js"}}))
    named_facts = inspect.inspect(str(named))
    assert "npm" in named_facts["ecosystems"]
    assert "npm install -g demo-cli" in named_facts["suggested_install_commands"]


def test_inspect_repo_cargo_install_uses_crate_name_not_npm_or_pypi_name(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")

    polyglot = tmp_path / "polyglot"
    polyglot.mkdir()
    (polyglot / "package.json").write_text(json.dumps({"name": "@org/web"}))
    (polyglot / "Cargo.toml").write_text('[package]\nname = "native-core"\n')
    polyglot_facts = inspect.inspect(str(polyglot))
    assert "cargo install native-core" in polyglot_facts["suggested_install_commands"]
    assert "cargo install @org/web" not in polyglot_facts["suggested_install_commands"]

    rust_only = tmp_path / "rust-only"
    rust_only.mkdir()
    (rust_only / "Cargo.toml").write_text('[package]\nname = "demo-cli"\n')
    rust_facts = inspect.inspect(str(rust_only))
    assert "cargo install demo-cli" in rust_facts["suggested_install_commands"]

    unnamed_crate = tmp_path / "unnamed-crate"
    unnamed_crate.mkdir()
    (unnamed_crate / "package.json").write_text(json.dumps({"name": "@org/web"}))
    (unnamed_crate / "pyproject.toml").write_text('[project]\nname = "demo-lib"\n')
    (unnamed_crate / "Cargo.toml").write_text("[package]\n")
    unnamed_facts = inspect.inspect(str(unnamed_crate))
    assert not any(cmd.startswith("cargo install") for cmd in unnamed_facts["suggested_install_commands"])


def test_inspect_repo_demo_media_includes_gif_beyond_first_20_images(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    for index in range(20):
        (tmp_path / f"shot-{index:02d}.png").write_bytes(b"")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "demo.gif").write_bytes(b"")
    (tmp_path / "clip.mp4").write_bytes(b"")
    (tmp_path / "loop.webm").write_bytes(b"")
    (tmp_path / "session.cast").write_bytes(b"")
    facts = inspect.inspect(str(tmp_path))
    assert "docs/demo.gif" in facts["demo_media"]
    assert len(facts["images"]) == 20
    assert "clip.mp4" in facts["demo_media"]
    assert "loop.webm" in facts["demo_media"]
    assert "session.cast" in facts["demo_media"]


def test_inspect_repo_cast_or_mp4_only_does_not_emit_no_images_gap(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    no_images = "No images in repo"

    empty = tmp_path / "empty"
    empty.mkdir()
    empty_facts = inspect.inspect(str(empty))
    assert empty_facts["images"] == []
    assert empty_facts["demo_media"] == []
    assert any(no_images in gap for gap in empty_facts["gaps"])

    for name in ("session.cast", "demo.mp4"):
        repo = tmp_path / name.replace(".", "-")
        repo.mkdir()
        (repo / name).write_bytes(b"")
        facts = inspect.inspect(str(repo))
        assert name in facts["demo_media"]
        assert facts["images"] == []
        assert not any(no_images in gap for gap in facts["gaps"])


def test_inspect_repo_omits_discord_webhook_urls_from_community_links(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    webhook = "https://discord.com/api/webhooks/111/exampletoken"
    invite = "https://discord.gg/abcdef"
    (tmp_path / "README.md").write_text(f"Join {invite} or hook {webhook}\n")
    (tmp_path / "package.json").write_text(json.dumps({"name": "demo", "homepage": webhook}))
    facts = inspect.inspect(str(tmp_path))
    assert invite in facts["community_links"]
    assert webhook not in facts["community_links"]
    assert "exampletoken" not in inspect.human(facts)
    result = subprocess.run(
        [sys.executable, str(INSPECT_SCRIPT), str(tmp_path), "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "exampletoken" not in result.stdout
    assert invite in result.stdout


def test_inspect_repo_www_homepage_is_not_docs(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    npm_url = "https://www.npmjs.com/package/demo"
    docs_url = "https://docs.example.com"
    no_docs = "No docs site or docs/ dir"

    www_repo = tmp_path / "www"
    www_repo.mkdir()
    (www_repo / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.1.0"\n')
    (www_repo / "README.md").write_text(f"See {npm_url}\n")
    www_facts = inspect.inspect(str(www_repo))
    assert npm_url not in www_facts["docs_links"]
    assert any(no_docs in gap for gap in www_facts["gaps"])
    assert www_facts["readme"]["links_docs_site"] is False

    docs_repo = tmp_path / "with-docs"
    docs_repo.mkdir()
    (docs_repo / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.1.0"\n')
    (docs_repo / "README.md").write_text(f"Docs: {docs_url}\n")
    docs_facts = inspect.inspect(str(docs_repo))
    assert docs_url in docs_facts["docs_links"]
    assert not any(no_docs in gap for gap in docs_facts["gaps"])
    assert docs_facts["readme"]["links_docs_site"] is True


def test_inspect_walk_skips_bulky_dirs(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    bulky = {"coverage", "htmlcov", ".gradle", "Pods", "data", "datasets"}
    assert bulky <= inspect.SKIP_DIRS

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo-lib"\nversion = "0.1.0"\n')
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for index in range(8):
        (data_dir / f"chunk-{index}.bin").write_bytes(b"x")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('ok')\n")

    walked = inspect.walk(str(tmp_path))
    assert not any(Path(path).parts[:1] == ("data",) for path in walked)
    assert any(path.endswith("main.py") for path in walked)

    facts = inspect.inspect(str(tmp_path))
    assert facts["name"] == "demo-lib"
    assert facts["file_count"] == len(walked)
    assert "chunk-0.bin" not in json.dumps(facts)


def test_score_readme_hero_requires_nonbadge_image_in_first_screen() -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    pad = "More context about this library. \n" * 80
    late = (
        "# demo-lib\n\n"
        "A library for testers who need a late screenshot.\n\n"
        "![ci](https://img.shields.io/badge/ci-passing-green)\n"
        f"{pad}"
        "![demo](docs/late.png)\n"
    )
    assert late.find("![demo](docs/late.png)") >= 1800
    assert late.find("shields.io") < 1800
    assert "```" not in late[:2500]
    late_hero = next(item for item in score.check(late)[0] if item["id"] == "hero")
    assert late_hero["ok"] is False

    early = "# demo-lib\n\nA library for testers who need a demo screenshot.\n\n![demo](docs/demo.png)\n"
    early_hero = next(item for item in score.check(early)[0] if item["id"] == "hero")
    assert early_hero["ok"] is True

    fenced = "# demo-lib\n\nA library for testers who read code first.\n\n```python\nprint('hello')\n```\n"
    fenced_hero = next(item for item in score.check(fenced)[0] if item["id"] == "hero")
    assert fenced_hero["ok"] is True


def test_score_readme_flags_placeholders_and_missing_install() -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    checks, stats = score.check(WEAK_README.read_text(), repo=str(SKILL_ROOT / "evals" / "files"))
    failed = {item["id"] for item in checks if not item["ok"]}
    assert "install" in failed
    assert "placeholders" in failed
    assert stats["lines"] > 0


def test_score_readme_accepts_python_m_pip_install() -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    md = "# demo-lib\n\nInstall it.\n\n```bash\npython -m pip install demo-lib\n```\n"
    checks, _stats = score.check(md)
    install = next(item for item in checks if item["id"] == "install")
    assert install["ok"] is True
    assert install["sev"] == "CRITICAL"

    no_cmd = "# demo-lib\n\nThis project has no install steps.\n"
    missing, _ = score.check(no_cmd)
    failed = {item["id"] for item in missing if not item["ok"]}
    assert "install" in failed


def test_score_readme_non_numeric_node_engines_does_not_crash(tmp_path: Path) -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    lts_repo = tmp_path / "lts"
    lts_repo.mkdir()
    (lts_repo / "package.json").write_text('{"name": "demo", "engines": {"node": "lts"}}\n')
    checks, stats = score.check("# demo\n\nRequires Node 18.\n", repo=str(lts_repo))
    assert isinstance(checks, list)
    assert isinstance(stats, dict)

    numeric_repo = tmp_path / "numeric"
    numeric_repo.mkdir()
    (numeric_repo / "package.json").write_text('{"name": "demo", "engines": {"node": ">=20"}}\n')
    checks_old, _ = score.check("# demo\n\nRequires Node 16.\n", repo=str(numeric_repo))
    failed = {item["id"] for item in checks_old if not item["ok"]}
    assert "manifest-consistency" in failed


def test_score_readme_numeric_or_non_dict_node_engines_does_not_crash(tmp_path: Path) -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    md = "# demo\n\nRequires Node 16.\n"

    numeric_repo = tmp_path / "numeric"
    numeric_repo.mkdir()
    (numeric_repo / "package.json").write_text('{"name": "demo", "engines": {"node": 20}}\n')
    numeric_checks, _ = score.check(md, repo=str(numeric_repo))
    assert isinstance(numeric_checks, list)

    string_engines_repo = tmp_path / "string-engines"
    string_engines_repo.mkdir()
    (string_engines_repo / "package.json").write_text('{"name": "demo", "engines": "node >= 20"}\n')
    string_checks, _ = score.check(md, repo=str(string_engines_repo))
    assert isinstance(string_checks, list)

    range_repo = tmp_path / "range"
    range_repo.mkdir()
    (range_repo / "package.json").write_text('{"name": "demo", "engines": {"node": ">=20"}}\n')
    range_checks, _ = score.check(md, repo=str(range_repo))
    failed = {item["id"] for item in range_checks if not item["ok"]}
    assert "manifest-consistency" in failed

    lts_repo = tmp_path / "lts"
    lts_repo.mkdir()
    (lts_repo / "package.json").write_text('{"name": "demo", "engines": {"node": "lts"}}\n')
    lts_checks, _ = score.check(md, repo=str(lts_repo))
    assert isinstance(lts_checks, list)
    assert "manifest-consistency" not in {item["id"] for item in lts_checks}

    silent_repo = tmp_path / "silent"
    silent_repo.mkdir()
    (silent_repo / "package.json").write_text('{"name": "demo", "engines": {"node": ">=20"}}\n')
    silent_md = "# demo\n\nA library for testers.\n\n```bash\nnpm i demo\n```\n"
    silent_checks, _ = score.check(silent_md, repo=str(silent_repo))
    assert "manifest-consistency" not in {item["id"] for item in silent_checks}


def test_score_readme_omits_manifest_consistency_when_readme_silent(tmp_path: Path) -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    repo = tmp_path / "py"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "demo"\nrequires-python = ">=3.12"\n')

    silent = "# demo\n\nA library for testers.\n\n```bash\npip install demo\n```\n"
    silent_checks, _ = score.check(silent, repo=str(repo))
    assert "manifest-consistency" not in {item["id"] for item in silent_checks}

    stated = "# demo\n\nRequires Python 3.9.\n\n```bash\npip install demo\n```\n"
    stated_checks, _ = score.check(stated, repo=str(repo))
    failed = {item["id"] for item in stated_checks if not item["ok"]}
    assert "manifest-consistency" in failed


def test_score_readme_broken_links_do_not_follow_paths_outside_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    repo = tmp_path / "proj"
    repo.mkdir()
    (repo / "LICENSE").write_text("MIT\n")
    repo_real = os.path.realpath(repo)

    probed: list[str] = []
    real_exists = score.os.path.exists

    def tracking_exists(path):
        probed.append(os.fspath(path))
        return real_exists(path)

    monkeypatch.setattr(score.os.path, "exists", tracking_exists)

    escaped = (
        "# demo\n\nA library for testers.\n\nSee [passwd](/etc/passwd) and [up](../../SomeFile).\n"
        "![logo](/etc/passwd)\n"
    )
    escaped_checks, _ = score.check(escaped, repo=str(repo))
    failed = {item["id"] for item in escaped_checks if not item["ok"]}
    assert "broken-links" in failed
    for path in probed:
        resolved = os.path.realpath(path)
        assert os.path.commonpath([repo_real, resolved]) == repo_real

    license_md = "# demo\n\nA library for testers.\n\nSee the [license](LICENSE).\n"
    present_checks, _ = score.check(license_md, repo=str(repo))
    present = next(item for item in present_checks if item["id"] == "broken-links")
    assert present["ok"] is True

    (repo / "LICENSE").unlink()
    missing_checks, _ = score.check(license_md, repo=str(repo))
    missing = next(item for item in missing_checks if item["id"] == "broken-links")
    assert missing["ok"] is False


def test_score_readme_github_image_fragments_are_not_broken_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    repo = tmp_path / "proj"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "demo.png").write_text("png\n")
    repo_real = os.path.realpath(repo)
    md = "# demo\n\nA library for testers who need a screenshot.\n\n![demo](docs/demo.png#gh-dark-mode-only)\n"

    present_checks, _ = score.check(md, repo=str(repo))
    present = next(item for item in present_checks if item["id"] == "broken-links")
    assert present["ok"] is True

    (docs / "demo.png").unlink()
    missing_checks, _ = score.check(md, repo=str(repo))
    missing = next(item for item in missing_checks if item["id"] == "broken-links")
    assert missing["ok"] is False

    probed: list[str] = []
    real_exists = score.os.path.exists

    def tracking_exists(path):
        probed.append(os.fspath(path))
        return real_exists(path)

    monkeypatch.setattr(score.os.path, "exists", tracking_exists)
    escaped = (
        "# demo\n\nA library for testers.\n\nSee [passwd](/etc/passwd) and [up](../../SomeFile).\n"
        "![logo](/etc/passwd)\n"
    )
    escaped_checks, _ = score.check(escaped, repo=str(repo))
    failed = {item["id"] for item in escaped_checks if not item["ok"]}
    assert "broken-links" in failed
    for path in probed:
        resolved = os.path.realpath(path)
        assert os.path.commonpath([repo_real, resolved]) == repo_real


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


def test_score_readme_caps_input_size(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A README larger than 200_000 bytes is truncated before scoring."""
    score = _load_module(SCORE_SCRIPT, "score_readme")
    readme = tmp_path / "README.md"
    readme.write_text("a\n" * 600_000 + "```bash\npip install demo\n```\n")
    text = score._read_text(str(readme))
    assert len(text) <= 200_000
    checks, stats = score.check(text)
    assert checks
    assert stats["lines"] > 0
    assert "truncat" in capsys.readouterr().err.lower()


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


def test_fetch_corpus_aborts_after_consecutive_github_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_inspect_repo_prefers_binary_name_over_git_slug(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    repo = tmp_path / "sandbox"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "remote", "add", "origin", "https://github.com/example/sandbox.git")
    (repo / "package.json").write_text(
        json.dumps({"name": "@org/sandbox", "private": True, "bin": {"msb-agent": "dist/cli.js"}})
    )
    facts = inspect.inspect(str(repo))
    assert facts["repo"] == "sandbox"
    assert facts["binary_names"] == ["msb-agent"]
    assert facts["name"] == "msb-agent"
    assert "msb-agent" in inspect.human(facts)


def test_inspect_repo_caps_binary_names_at_fifteen(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    repo = tmp_path / "sandbox"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "remote", "add", "origin", "https://github.com/example/sandbox.git")
    bins = {f"cli{i:02d}": "cli.js" for i in range(40)}
    (repo / "package.json").write_text(json.dumps({"name": "@org/sandbox", "private": True, "bin": bins}))
    facts = inspect.inspect(str(repo))
    expected = [f"cli{i:02d}" for i in range(15)]
    assert facts["binary_names"] == expected
    assert facts["name"] == "cli00"
    assert facts["repo"] == "sandbox"
    sheet = inspect.human(facts)
    assert "cli00" in sheet
    assert "cli39" not in sheet
    assert "cli15" not in sheet


def test_inspect_repo_caps_just_recipes_at_fifteen(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    recipes = ["install:\n    npm ci\n", "build:\n    npm run build\n"]
    extra = 0
    size = sum(len(chunk) + 1 for chunk in recipes)
    while size < 200_000:
        line = f"r{extra}:\n    true\n"
        recipes.append(line)
        size += len(line) + 1
        extra += 1
    (tmp_path / "justfile").write_text("\n".join(recipes))
    (tmp_path / "package.json").write_text(json.dumps({"name": "demo", "private": True, "bin": {"demo": "cli.js"}}))
    facts = inspect.inspect(str(tmp_path))
    assert facts["just_recipes"] == ["install", "build"] + [f"r{i}" for i in range(13)]
    assert len(facts["just_recipes"]) == 15
    assert facts["suggested_install_commands"] == ["just install"]
    assert "just build" not in facts["suggested_install_commands"]
    assert facts["suggested_run_commands"][0] == "just build"
    sheet = inspect.human(facts)
    assert "r12" in sheet
    assert f"r{extra - 1}" not in sheet


def test_recipe_names_stops_after_fifteen_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")

    def no_findall(*_args, **_kwargs):
        raise AssertionError("findall materializes every recipe name")

    monkeypatch.setattr(inspect.re, "findall", no_findall)
    text = "".join(f"r{i}:\n" for i in range(40))
    assert inspect._recipe_names(text) == [f"r{i}" for i in range(15)]


def test_inspect_repo_prefers_console_scripts_over_project_name(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo-lib"\nversion = "0.1.0"\n\n'
        '[project.scripts]\ndemo = "demo:main"\n\n'
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n'
        'target-version = "3.12"\n'
    )
    facts = inspect.inspect(str(tmp_path))
    assert facts["binary_names"] == ["demo"]
    assert facts["name"] == "demo"
    sheet = inspect.human(facts)
    assert "demo" in sheet
    assert "build-backend" not in sheet
    assert "target-version" not in sheet


def test_inspect_repo_empty_console_scripts_keep_project_name(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo-lib"\nversion = "0.1.0"\n\n'
        "[project.scripts]\n# no entry points\n\n"
        '[build-system]\nbuild-backend = "hatchling.build"\n'
    )
    facts = inspect.inspect(str(tmp_path))
    assert facts["binary_names"] == []
    assert facts["name"] == "demo-lib"


def test_inspect_repo_caps_console_scripts_at_fifteen(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    scripts = "\n".join(f'script{i:02d} = "demo:main{i}"' for i in range(40))
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "demo-lib"\nversion = "0.1.0"\n\n[project.scripts]\n{scripts}\n'
    )
    facts = inspect.inspect(str(tmp_path))
    expected = [f"script{i:02d}" for i in range(15)]
    assert facts["binary_names"] == expected
    assert facts["console_scripts"] == expected
    assert len(facts["binary_names"]) == 15
    assert len(facts["console_scripts"]) == 15
    assert facts["name"] == "script00"
    sheet = inspect.human(facts)
    dumped = json.dumps(facts)
    assert "script00" in sheet and "script14" in sheet
    assert "script15" not in sheet and "script39" not in sheet
    assert "script00" in dumped and "script14" in dumped
    assert "script15" not in dumped and "script39" not in dumped


def test_inspect_repo_caps_pyproject_binary_names_at_fifteen(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    scripts = "\n".join(f'script{i:02d} = "demo:main{i}"' for i in range(16))
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "demo-lib"\nversion = "0.1.0"\n\n[project.scripts]\n{scripts}\n'
    )
    facts = inspect.inspect(str(tmp_path))
    assert facts["binary_names"] == [f"script{i:02d}" for i in range(15)]
    assert facts["name"] == "script00"


def test_console_scripts_stops_after_fifteen_matches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")

    def no_findall(*_args, **_kwargs):
        raise AssertionError("findall materializes every console script name")

    monkeypatch.setattr(inspect.re, "findall", no_findall)
    lines = [f's{i} = "pkg:m{i}"\n' for i in range(15)]
    extra = 0
    size = sum(len(line) for line in lines)
    while size < 200_000:
        line = f'pad{extra} = "pkg:p{extra}"\n'
        lines.append(line)
        size += len(line)
        extra += 1
    (tmp_path / "pyproject.toml").write_text("[project.scripts]\n" + "".join(lines))
    facts: dict = {}
    inspect._manifest_facts(str(tmp_path), ["pyproject.toml"], facts)
    assert facts["console_scripts"] == [f"s{i}" for i in range(15)]
    assert facts["binary_names"] == [f"s{i}" for i in range(15)]


def test_inspect_repo_reports_justfile_recipes(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    (tmp_path / "justfile").write_text("install:\n    npm ci\n\nbuild:\n    npm run build\n\nimages:\n    echo hi\n")
    (tmp_path / "package.json").write_text(json.dumps({"name": "demo", "private": True, "bin": {"demo": "cli.js"}}))
    facts = inspect.inspect(str(tmp_path))
    assert facts["just_recipes"] == ["install", "build", "images"]
    assert facts["suggested_install_commands"] == ["just install"]
    assert "just build" not in facts["suggested_install_commands"]
    assert facts["suggested_run_commands"][0] == "just build"
    sheet = inspect.human(facts)
    assert "JUST" in sheet
    assert "install" in sheet


def test_inspect_repo_parameterized_just_install_recipe(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    (tmp_path / "justfile").write_text(
        'foo := "bar"\n\n'
        "install *args:\n    uv sync {{args}}\n\n"
        "release version:\n    echo {{version}}\n\n"
        "add_skill *args:\n    echo {{args}}\n"
    )
    facts = inspect.inspect(str(tmp_path))
    assert "install" in facts["just_recipes"]
    assert "release" in facts["just_recipes"]
    assert "add_skill" in facts["just_recipes"]
    assert "foo" not in facts["just_recipes"]
    assert facts["suggested_install_commands"] == ["just install"]


def test_inspect_repo_registry_install_stays_ahead_of_just_recipes(tmp_path: Path) -> None:
    inspect = _load_module(INSPECT_SCRIPT, "inspect_repo")
    justfile = "install:\n    npm ci\n\nbuild:\n    npm run build\n"

    npm = tmp_path / "npm"
    npm.mkdir()
    (npm / "justfile").write_text(justfile)
    (npm / "package.json").write_text(json.dumps({"name": "demo", "bin": {"demo": "cli.js"}}))
    npm_facts = inspect.inspect(str(npm))
    assert npm_facts["suggested_install_commands"][0] == "npm install -g demo"
    assert not any(cmd.startswith("just ") for cmd in npm_facts["suggested_install_commands"])
    assert npm_facts["just_recipes"] == ["install", "build"]

    pypi = tmp_path / "pypi"
    pypi.mkdir()
    (pypi / "justfile").write_text("install:\n    uv sync\n")
    (pypi / "pyproject.toml").write_text('[project]\nname = "demo-lib"\n')
    pypi_facts = inspect.inspect(str(pypi))
    assert pypi_facts["suggested_install_commands"][0] == "pip install demo-lib"
    assert not any(cmd.startswith("just ") for cmd in pypi_facts["suggested_install_commands"])
    assert pypi_facts["just_recipes"] == ["install"]


def _cli_catalog_fence(n_cmds: int) -> str:
    chunks = [f"# Run command {i}\ndemo sub{i}\n" for i in range(n_cmds)]
    chunks.append("# List all options and other usage\ndemo --help\n")
    return "```bash\n" + "\n".join(chunks) + "```\n"


def _cli_readme_body(quick_start: str) -> str:
    return (
        "# demo\n\n"
        "A CLI for testers who need a command catalog.\n\n"
        "## Features\n\n"
        "- **Fast.** Starts in one command.\n"
        "- **Offline.** No network required.\n"
        "- **Single binary.** No runtime.\n\n"
        "## Installation\n\n"
        "```bash\npip install demo\n```\n\n"
        "## Quick start\n\n"
        f"{quick_start}\n"
        "## Documentation\n\n"
        "See [docs](https://example.com).\n\n"
        "## Contributing\n\n"
        "See CONTRIBUTING.md.\n\n"
        "## License\n\n"
        "MIT\n"
    )


def test_capped_cli_catalog_with_overflow_stays_in_length_band() -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    extra = "\n".join(f"# Extra {i}\ndemo extra{i}\n" for i in range(32))
    overflow = f"<details>\n<summary>More commands</summary>\n\n```bash\n{extra}```\n\n</details>\n"
    md = _cli_readme_body(_cli_catalog_fence(8) + overflow)
    length_item = next(item for item in score.check(md)[0] if item["id"] == "length")
    assert length_item["ok"] is True
    assert 50 <= md.count("\n") + 1 <= 320


def _expected_output_ok(score: ModuleType, md: str) -> bool:
    return next(item["ok"] for item in score.check(md)[0] if item["id"] == "expected-output")


def test_score_readme_commented_cli_catalog_counts_as_expected_output() -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    catalog = (
        "# demo\n\nA CLI for testers who need a command catalog.\n\n"
        "```bash\n# Start the tool in this directory\ndemo run\n\n"
        "# List all options and other usage\ndemo --help\n```\n"
    )
    assert _expected_output_ok(score, catalog) is True

    quick_start = (
        "# demo\n\nA CLI for testers who need a command catalog.\n\n"
        "## Quick start\n\n"
        "```bash\n# Start the tool in this directory\ndemo run\n\n"
        "# Run a second real invocation\ndemo build\n```\n"
    )
    assert _expected_output_ok(score, quick_start) is True

    extras = "```bash\n# Homebrew\nbrew install demo\n\n# Docker\ndocker run demo\n\n# From source\nmake install\n```\n"
    extras_only = "# demo\n\nA CLI for testers who need a command catalog.\n\n" + extras
    assert _expected_output_ok(score, extras_only) is False

    extras_in_details = (
        "# demo\n\nA CLI for testers who need a command catalog.\n\n"
        "<details>\n<summary>Other install methods</summary>\n\n"
        f"{extras}\n</details>\n"
    )
    assert _expected_output_ok(score, extras_in_details) is False

    weak_details = (
        "# demo-tool\n\nLaunch CLI coding agents inside guest VMs.\n\n"
        "<details>\n<summary>Without just, and extra images</summary>\n\n"
        "```bash\n# CLI only\ncd packages/demo && npm ci && npm run build\n\n"
        "# Build images\njust images\n```\n\n</details>\n"
    )
    assert _expected_output_ok(score, weak_details) is False
    assert score._commented_shell_catalog(CLI_WEAK_README.read_text()) is False

    lone = "# demo\n\nA library for testers.\n\n```python\nprint('hello')\n```\n"
    assert _expected_output_ok(score, lone) is False


def test_score_readme_getting_started_install_extras_are_not_a_catalog() -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    extras = "```bash\n# Homebrew\nbrew install demo\n\n# Docker\ndocker run demo\n\n# From source\nmake install\n```\n"

    getting_started = "# demo\n\nA CLI for testers who need a command catalog.\n\n## Getting started\n\n" + extras
    assert _expected_output_ok(score, getting_started) is False

    extras_only = "# demo\n\nA CLI for testers who need a command catalog.\n\n" + extras
    assert _expected_output_ok(score, extras_only) is False

    extras_in_details = (
        "# demo\n\nA CLI for testers who need a command catalog.\n\n"
        "<details>\n<summary>Other install methods</summary>\n\n"
        f"{extras}\n</details>\n"
    )
    assert _expected_output_ok(score, extras_in_details) is False

    quick_start_extras = "# demo\n\nA CLI for testers who need a command catalog.\n\n## Quick start\n\n" + extras
    assert _expected_output_ok(score, quick_start_extras) is False

    quick_start = (
        "# demo\n\nA CLI for testers who need a command catalog.\n\n"
        "## Quick start\n\n"
        "```bash\n# Start the tool in this directory\ndemo run\n\n"
        "# List all options and other usage\ndemo --help\n```\n"
    )
    assert _expected_output_ok(score, quick_start) is True


def test_score_readme_npx_or_uvx_catalog_ending_in_help_counts_as_expected_output() -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    uvx_catalog = (
        "# demo\n\nA CLI for testers who need a command catalog.\n\n"
        "## Quick start\n\n"
        "```bash\n# Run\nuvx ruff check\n\n# List options\nuvx ruff --help\n```\n"
    )
    assert _expected_output_ok(score, uvx_catalog) is True

    npx_catalog = (
        "# demo\n\nA CLI for testers who need a command catalog.\n\n"
        "## Quick start\n\n"
        "```bash\n# Run\nnpx eslint .\n\n# List options\nnpx eslint --help\n```\n"
    )
    assert _expected_output_ok(score, npx_catalog) is True

    extras = "```bash\n# Homebrew\nbrew install demo\n\n# Docker\ndocker run demo\n\n# From source\nmake install\n```\n"
    extras_only = "# demo\n\nA CLI for testers who need a command catalog.\n\n" + extras
    assert _expected_output_ok(score, extras_only) is False

    getting_started = "# demo\n\nA CLI for testers who need a command catalog.\n\n## Getting started\n\n" + extras
    assert _expected_output_ok(score, getting_started) is False

    quick_start_extras = "# demo\n\nA CLI for testers who need a command catalog.\n\n## Quick start\n\n" + extras
    assert _expected_output_ok(score, quick_start_extras) is False


def test_score_readme_accepts_just_install() -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    md = "# demo\n\nInstall it.\n\n```bash\njust install\njust build\n```\n"
    install = next(item for item in score.check(md)[0] if item["id"] == "install")
    assert install["ok"] is True


def test_score_readme_without_summary_must_not_reuse_token() -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    bad = (
        "# demo\n\nA CLI for testers.\n\n```bash\njust install\n```\n\n"
        "<details>\n<summary>Without just, and extra images</summary>\n\n"
        "```bash\nnpm ci\njust images\n```\n\n</details>\n"
    )
    bad_item = next(item for item in score.check(bad)[0] if item["id"] == "without-details")
    assert bad_item["ok"] is False
    assert "Without X" in bad_item["msg"]

    good = (
        "# demo\n\nA CLI for testers.\n\n```bash\njust install\njust build\n```\n\n"
        "<details>\n<summary>Other install methods</summary>\n\n"
        "```bash\nbrew install demo\n```\n\n</details>\n"
    )
    good_item = next(item for item in score.check(good)[0] if item["id"] == "without-details")
    assert good_item["ok"] is True
    assert "Without X" in good_item["msg"]

    none = "# demo\n\nA CLI for testers.\n\n```bash\njust install\n```\n"
    none_item = next(item for item in score.check(none)[0] if item["id"] == "without-details")
    assert none_item["ok"] is True
    assert "Without X" in none_item["msg"]


def test_score_readme_without_summary_skips_articles_and_using() -> None:
    score = _load_module(SCORE_SCRIPT, "score_readme")
    gpu = (
        "# demo\n\nA CLI for testers.\n\n```bash\njust install\n```\n\n"
        "<details>\n<summary>Without a GPU</summary>\n\n"
        "This path uses a laptop CPU only.\n\n"
        "```bash\nnpm ci\nnpm run build\n```\n\n</details>\n"
    )
    gpu_item = next(item for item in score.check(gpu)[0] if item["id"] == "without-details")
    assert gpu_item["ok"] is True

    using_just = (
        "# demo\n\nA CLI for testers.\n\n```bash\njust install\n```\n\n"
        "<details>\n<summary>Without using just</summary>\n\n"
        "```bash\njust images\n```\n\n</details>\n"
    )
    using_item = next(item for item in score.check(using_just)[0] if item["id"] == "without-details")
    assert using_item["ok"] is False

    existing = (
        "# demo\n\nA CLI for testers.\n\n```bash\njust install\n```\n\n"
        "<details>\n<summary>Without just, and extra images</summary>\n\n"
        "```bash\nnpm ci\njust images\n```\n\n</details>\n"
    )
    existing_item = next(item for item in score.check(existing)[0] if item["id"] == "without-details")
    assert existing_item["ok"] is False
