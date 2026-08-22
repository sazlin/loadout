"""Contracts and colocated evals for the github-upload-media-to-pr skill."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from loadout.frontmatter import parse_skill_md
from loadout.models import load_loadout
from loadout.sync import sync

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO / "skills" / "github-upload-media-to-pr"
SKILL_MD = SKILL_ROOT / "SKILL.md"
SKILL_NAME = "github-upload-media-to-pr"
HOSTED_ARTIFACT_URL = "https://cursor.com/artifacts/c/art-"
STAGING_PATH_QUERY = "artifacts?path=/opt/cursor/artifacts"


def _evals_payload() -> dict[str, object]:
    path = SKILL_ROOT / "evals" / "evals.json"
    assert path.is_file(), path
    payload = json.loads(path.read_text())
    assert isinstance(payload, dict)
    return payload


def _eval_entry_texts(entry: dict[str, object]) -> str:
    chunks = [str(entry.get("prompt", "")), str(entry.get("expected_output", ""))]
    expectations = entry.get("expectations")
    if isinstance(expectations, list):
        chunks.extend(str(item) for item in expectations)
    return "\n".join(chunks).lower()


def _eval_texts(payload: dict[str, object]) -> str:
    raw = payload.get("evals")
    if not isinstance(raw, list):
        return ""
    chunks: list[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        chunks.append(_eval_entry_texts(entry))
    return "\n".join(chunks)


def _eval_by_id(payload: dict[str, object], eval_id: int) -> str:
    raw = payload.get("evals")
    assert isinstance(raw, list)
    for entry in raw:
        if isinstance(entry, dict) and entry.get("id") == eval_id:
            return _eval_entry_texts(entry)
    raise AssertionError(f"missing eval id {eval_id}")


def test_github_upload_media_skill_parses() -> None:
    assert SKILL_MD.is_file(), SKILL_MD
    meta = parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name=SKILL_NAME)
    assert meta.name == SKILL_NAME
    assert meta.license == "MIT"


def test_github_loadout_ships_upload_media_skill() -> None:
    loadout = load_loadout(REPO / "loadouts" / "github.yaml")
    assert loadout.name == "github"
    assert loadout.extends == ["base"]
    assert {entry["src"] for entry in loadout.skills} == {f"skills/{SKILL_NAME}"}
    assert loadout.rules == []
    assert loadout.agents == []
    assert loadout.mcps == []


def test_base_loadout_does_not_include_github_upload_media_skill() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.skills}
    assert f"skills/{SKILL_NAME}" not in srcs


def _when_to_use_trigger_and_skip(text: str) -> tuple[str, str]:
    """Split the When-to-use section into trigger copy and the Skip paragraph."""
    lowered = text.lower()
    _, found, after = lowered.partition("## when to use")
    assert found, "SKILL.md is missing ## When to use"
    section, _, _ = after.partition("\n## ")
    trigger, skip_mark, skip = section.partition("**skip**")
    assert skip_mark, "When to use is missing a **Skip** rule"
    return trigger, skip


def _option_b_section(text: str) -> str:
    """Return the lowercased Option B comment-attach section."""
    lowered = text.lower()
    _, found, after = lowered.partition("option b")
    assert found, "SKILL.md is missing Option B"
    section, _, _ = after.partition("\n## ")
    return section


def _section_after_heading(text: str, heading: str) -> str:
    """Return the lowercased body of a markdown heading until the next h2."""
    lowered = text.lower()
    _, found, after = lowered.partition(heading)
    assert found, f"SKILL.md is missing {heading}"
    section, _, _ = after.partition("\n## ")
    return section


def test_description_triggers_on_media_and_pr_phrases() -> None:
    meta = parse_skill_md(SKILL_MD, SKILL_MD.read_text(), dir_name=SKILL_NAME)
    lowered = meta.description.lower()
    assert "pull request" in lowered or "pr" in lowered
    assert "screenshot" in lowered
    assert "video" in lowered or "recording" in lowered
    assert "put the screenshot in the pr" in lowered


def test_description_requires_explicit_pr_attach_request() -> None:
    """Walkthrough artifacts and generic test results are not a standalone attach trigger."""
    text = SKILL_MD.read_text()
    description = parse_skill_md(SKILL_MD, text, dir_name=SKILL_NAME).description.lower()
    trigger, skip = _when_to_use_trigger_and_skip(text)
    standalone_triggers = (
        "test results",
        "walkthrough",
        "visual evidence",
        "before/after",
    )
    for phrase in standalone_triggers:
        assert phrase not in description
        assert phrase not in trigger
    collapsed_skip = " ".join(skip.split())
    assert "asked" in description
    assert "user" in trigger
    assert "ask" in trigger or "want" in trigger
    assert "walkthrough" in skip
    assert "test results" in skip
    assert "do not attach" in collapsed_skip or "do not use" in collapsed_skip
    assert "computeruse" in skip
    assert "recordscreen" in skip
    assert "managepullrequest" in skip


def test_body_uses_cursor_cloud_attach_not_agent_browser() -> None:
    text = SKILL_MD.read_text()
    lowered = text.lower()
    assert "managepullrequest" in lowered
    assert "/opt/cursor/artifacts/" in lowered
    assert "computeruse" in lowered
    assert "recordscreen" in lowered
    assert "<img" in lowered
    assert "<video" in lowered
    assert "npx skills add" in lowered
    assert "npm i -g agent-browser" in lowered
    assert "do not" in lowered
    assert "gh pr comment" in lowered
    assert "gh pr edit" in lowered


def test_stage_copy_is_artifacts_only_after_mime_refuse() -> None:
    """Mime-type and secret-path refuse must run before any copy; dest is artifacts only."""
    text = SKILL_MD.read_text()
    lowered = text.lower()

    _, found, after = lowered.partition("## step 0")
    assert found, "SKILL.md is missing ## Step 0"
    step0, _, _ = after.partition("\n## ")

    assert "file --mime-type" in step0
    assert "do not copy" in step0
    assert "stop" in step0
    assert "refuse" in step0
    assert "/opt/cursor/artifacts/" in step0
    assert "safe-basename" in step0
    for needle in (".env", "id_rsa", "credentials", ".pem", ".key", ".git", "token"):
        assert needle in step0

    offset = 0
    first_cp_at: int | None = None
    for raw_line in text.splitlines(keepends=True):
        stripped = raw_line.strip()
        if stripped.startswith("cp "):
            dest = stripped.split()[-1]
            assert dest.startswith("/opt/cursor/artifacts/"), dest
            if first_cp_at is None:
                first_cp_at = offset
        offset += len(raw_line)
    assert first_cp_at is not None

    assert lowered.index("file --mime-type") < first_cp_at
    assert lowered.index("do not copy") < first_cp_at
    assert lowered.index("refuse") < first_cp_at

    simple = "copy it to a simple name first"
    if simple in lowered:
        idx = lowered.index(simple)
        nearby = lowered[max(0, idx - 80) : idx + len(simple) + 80]
        assert "/opt/cursor/artifacts/" in nearby

    assert simple not in step0 or "/opt/cursor/artifacts/" in step0


def test_body_bounds_artifact_size_and_count() -> None:
    """Max bytes-per-file and file count must be stated before any cp or update_pr."""
    text = SKILL_MD.read_text()
    lowered = text.lower()

    first_cp_at: int | None = None
    first_update_pr_at: int | None = None
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        stripped = raw_line.strip()
        if first_cp_at is None and stripped.startswith("cp "):
            first_cp_at = offset
        if first_update_pr_at is None and "update_pr" in raw_line.lower():
            first_update_pr_at = offset
        offset += len(raw_line)
    assert first_cp_at is not None
    assert first_update_pr_at is not None
    gate = lowered[: min(first_cp_at, first_update_pr_at)]

    size_match = re.search(r"\b(\d+)\s*(mb|mib|bytes)\b", gate)
    assert size_match, "missing max bytes-per-file before cp/update_pr"
    assert int(size_match.group(1)) > 0

    count_match = re.search(r"\b(\d+)\s+files?\b", gate)
    assert count_match, "missing max file count before cp/update_pr"
    assert int(count_match.group(1)) > 0

    assert "stat" in gate
    assert "refuse" in gate or "skip" in gate
    assert "do not copy" in gate


def test_body_bounds_recording_duration_and_discard() -> None:
    """RecordScreen must have a numeric max duration and DISCARD on capture hang."""
    text = SKILL_MD.read_text()
    lowered = text.lower()
    _, found, after = lowered.partition("## capturing media")
    assert found, "SKILL.md is missing a capturing-media section"
    capture, _, _ = after.partition("\n## ")

    duration = re.search(r"\b(\d+)\s*seconds?\b", capture)
    assert duration, "missing numeric max recording duration"
    assert int(duration.group(1)) > 0
    assert "discard_recording" in capture
    assert "save_recording" in capture
    assert "does not return" in capture or "hang" in capture or "timeout" in capture or "deadline" in capture
    assert "already on disk" in capture or "files already" in capture
    assert "exercise the ui, save" not in capture


def test_capture_and_on_disk_paths_start_at_step_0() -> None:
    """Capture and already-on-disk files must run Step 0 before any Stage/cp."""
    text = SKILL_MD.read_text()
    capture = _section_after_heading(text, "## capturing media")
    collapsed_capture = " ".join(capture.split())
    assert "start at step 1" not in collapsed_capture
    assert "begin at step 1" not in collapsed_capture

    bullets = [f"- {part}" if not part.startswith("-") else part for part in capture.split("\n- ")]
    screenshot = next((b for b in bullets if "screenshot" in b), "")
    video = next((b for b in bullets if "recordscreen" in b or "demo video" in b), "")
    on_disk = next((b for b in bullets if "already-on-disk" in b), "")
    assert screenshot and video and on_disk

    for name, bullet in (("screenshot", screenshot), ("video", video), ("on_disk", on_disk)):
        collapsed = " ".join(bullet.split())
        assert "step 0" in collapsed, f"{name} must run Step 0"
        stage_at = collapsed.find("stage")
        if stage_at != -1:
            assert collapsed.find("step 0") < stage_at, f"{name} stages before Step 0"

    assert "discard_recording" in video
    discard_at = video.find("discard_recording")
    assert "step 0" in video[discard_at:]

    step1 = _section_after_heading(text, "## step 1")
    collapsed_step1 = " ".join(step1.split())
    assert re.search(r"been run and passed|run and passed", collapsed_step1)
    assert "do not copy" in collapsed_step1 or "forbidden" in collapsed_step1

    troubleshooting = _section_after_heading(text, "## troubleshooting")
    special = next((line for line in troubleshooting.splitlines() if "special character" in line), "")
    assert special and "step 0" in special

    eval1 = _eval_by_id(_evals_payload(), 1)
    assert "mime" in eval1
    assert "secret" in eval1
    assert eval1.index("refuse") < eval1.index("copy")


def test_body_comment_video_uses_rewritten_host_not_staging_path() -> None:
    """Option B comment examples must use hosted art- URLs, not staging-path queries."""
    option_b = _option_b_section(SKILL_MD.read_text())
    examples = re.findall(r"```markdown\n(.*?)```", option_b, flags=re.DOTALL)
    assert examples, "Option B is missing markdown comment examples"
    for example in examples:
        assert HOSTED_ARTIFACT_URL in example
        assert STAGING_PATH_QUERY not in example
        assert "/opt/cursor/artifacts/" not in example
    assert STAGING_PATH_QUERY not in option_b


def test_body_stages_via_update_pr_before_post_comment() -> None:
    """Option B must stage with update_pr before post_comment using rewritten hosts."""
    option_b = _option_b_section(SKILL_MD.read_text())
    assert "update_pr" in option_b
    assert "post_comment" in option_b
    assert option_b.index("update_pr") < option_b.rindex("post_comment")
    collapsed = " ".join(option_b.replace("*", "").split())
    assert "do not send" in collapsed
    assert "/opt/cursor/artifacts/" in option_b
    assert "first" in option_b
    assert HOSTED_ARTIFACT_URL in option_b
    assert STAGING_PATH_QUERY not in option_b


def test_body_labels_cleanup_update_pr_not_attach_retry() -> None:
    """Option B's second update_pr is labeled cleanup, not an attach rewrite retry."""
    text = SKILL_MD.read_text()
    step3 = _section_after_heading(text, "## step 3")
    collapsed_step3 = " ".join(step3.split())
    assert re.search(
        r"attach[`\s]+update_pr",
        collapsed_step3,
    ), "Option A must name the first call the attach update_pr"
    assert "do not retry" in collapsed_step3

    option_b = _option_b_section(text)
    collapsed_b = " ".join(option_b.split())
    assert re.search(
        r"(cleanup|remove-section).{0,80}update_pr|update_pr.{0,80}(cleanup|remove-section)",
        collapsed_b,
    ), "Option B must label the second update_pr as cleanup/remove-section"
    assert "retry" in collapsed_b
    assert "staging" in collapsed_b


def test_body_fail_closed_on_artifact_host() -> None:
    """One update_pr per attach; a failed rewrite stops and does not retry."""
    text = SKILL_MD.read_text()
    lowered = text.lower()

    _, found, after = lowered.partition("## step 3")
    assert found, "SKILL.md is missing ## Step 3"
    step3, _, _ = after.partition("\n## ")
    collapsed_step3 = " ".join(step3.split())
    assert re.search(
        r"(once|single).{0,60}update_pr|update_pr.{0,60}(once|single)",
        collapsed_step3,
    ), "Step 3 must state a single update_pr attempt"
    assert "hosting failed" in collapsed_step3
    assert "do not retry" in collapsed_step3
    assert "do not" in collapsed_step3 and "recording" in collapsed_step3
    assert "do not loop" in collapsed_step3 or "do not re-run" in collapsed_step3

    option_b = _option_b_section(text)
    collapsed_b = " ".join(option_b.split())
    assert "skip" in collapsed_b
    assert "post_comment" in option_b
    assert HOSTED_ARTIFACT_URL in option_b

    _, ts_found, ts_after = lowered.partition("## troubleshooting")
    assert ts_found, "SKILL.md is missing ## Troubleshooting"
    troubleshooting, _, _ = ts_after.partition("\n## ")
    collapsed_ts = " ".join(troubleshooting.split())
    assert "hosting failed" in collapsed_ts
    assert "do not retry" in collapsed_ts
    assert "use an absolute" not in collapsed_ts


def test_body_does_not_instruct_installing_agent_browser() -> None:
    text = SKILL_MD.read_text()
    lowered = text.lower()
    install_needles = (
        "npx skills add vercel-labs/agent-browser -g -y",
        "npm i -g agent-browser && agent-browser install",
    )
    for needle in install_needles:
        assert needle in lowered
    before_do_not, _, _ = lowered.partition("## do not")
    assert "npx skills add vercel-labs/agent-browser" not in before_do_not
    assert "npm i -g agent-browser && agent-browser install" not in before_do_not


def test_has_colocated_evals() -> None:
    payload = _evals_payload()
    assert payload["skill_name"] == SKILL_NAME
    evals = payload.get("evals")
    assert isinstance(evals, list) and evals
    for index, entry in enumerate(evals):
        assert isinstance(entry, dict)
        files = entry.get("files")
        if not isinstance(files, list):
            continue
        for relative in files:
            assert isinstance(relative, str)
            path = SKILL_ROOT / relative
            assert path.is_file(), f"{SKILL_NAME} evals[{index}] missing {relative}"


def test_evals_cover_img_video_and_install_refusal() -> None:
    payload = _evals_payload()
    texts = _eval_texts(payload)
    assert "/opt/cursor/artifacts/" in texts
    assert "managepullrequest" in texts
    assert "img" in texts
    assert "video" in texts
    assert "post_comment" in texts
    assert "npx skills add" in texts
    assert "npm i -g" in texts
    assert "does not run" in texts or "refuse" in texts
    comment_eval = _eval_by_id(payload, 2)
    assert "update_pr" in comment_eval
    assert "first attach" in comment_eval
    assert HOSTED_ARTIFACT_URL in comment_eval
    assert STAGING_PATH_QUERY in comment_eval


def test_github_sync_vendors_skill_without_evals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [github]\n")
    sync(project)
    dest = project / ".claude/skills" / SKILL_NAME / "SKILL.md"
    assert dest.is_file()
    assert "ManagePullRequest" in dest.read_text()
    assert not (project / ".claude/skills" / SKILL_NAME / "evals").exists()
    assert (project / ".claude/agents/davinci.md").is_file()


def test_base_sync_does_not_vendor_github_upload_media_skill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOADOUT_PATH", str(REPO))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".loadout.yaml").write_text("source: https://github.com/sazlin/loadout\nref: main\nloadouts: [base]\n")
    sync(project)
    assert not (project / ".claude/skills" / SKILL_NAME).exists()
