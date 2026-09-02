"""Evals and contracts for dimensional review agents."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from loadout.frontmatter import AgentMeta, parse_agent_md
from loadout.models import load_loadout

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from review_eval_score import (
    AGENTS_DIR,
    REVIEW_AGENTS,
    eval_by_id,
    evals_path,
    evals_root,
    load_blank_run,
    load_evals,
    load_golden,
    parse_report,
    score_behavior,
    score_blob_report,
    score_dimension_report,
    score_orchestrator_report,
)

REPO = _TESTS.parent
AGENTS = REPO / "agents"

IMPLEMENTATION_AGENTS = frozenset(
    {
        "python_coder.md",
        "davinci.md",
        "playwright_planner.md",
        "playwright_generator.md",
        "playwright_healer.md",
    }
)
REVIEW_DIMENSION_AGENTS = frozenset(
    {
        "review_correctness.md",
        "review_maintainability.md",
        "review_scale.md",
        "review_security.md",
    }
)
REVIEW_ORCHESTRATOR = "review_orchestrator.md"
ISSUE_RESOLVER = "issue_resolver.md"
VERIFIER = "verifier.md"
RISK_CLASSIFIER = "risk_classifier.md"
HARNESS_AGENTS = frozenset({ISSUE_RESOLVER, VERIFIER, RISK_CLASSIFIER})
IMPLEMENTATION_HARNESS_AGENTS = frozenset(
    {
        "implementation_orchestrator.md",
        "implementation_planner.md",
        "implementation_plan_reviewer.md",
        "implementation_builder.md",
        "implementation_build_reviewer.md",
    }
)

REVIEW_HEADINGS = [
    "## Charter",
    "## I/O contract",
    "## Definition of done",
    "## Tools / privileges",
    "## Anti-reward-hacking",
    "## Blocked protocol",
    "## Context acquisition",
    "## Repo conventions",
    "## Working style",
    "## Agent-specific guidance",
    "## Output schema",
]
REVIEW_TOOLS = {"Read", "Grep", "Glob", "Bash"}
WRITE_TOOLS = {"Edit", "Write"}
# Extra computerUse allowlist so a reviewer can observe a running web UI.
# Live exploration uses npx playwright-cli via Bash (the browser CLI the
# playwright loadout installs). Task is omitted: it can spawn write-capable
# agents. No Playwright MCP.
WEBAPP_REVIEW_TOOLS = {"computerUse"}
# review_maintainability, review_scale, review_orchestrator, and
# risk_classifier stay on REVIEW_TOOLS.
WEBAPP_REVIEW_AGENTS = frozenset(
    {
        "review_correctness.md",
        "review_security.md",
        "verifier.md",
    }
)
_FORBID_WORDS = ("forbid", "never", "do not")
_SECRET_DUMP_CLI = (
    "cookie-list",
    "cookie-get",
    "localstorage-list",
    "localstorage-get",
    "sessionstorage-get",
    "eval",
    "run-code",
)
ISSUE_SCHEMA_FIELDS = (
    '"id"',
    '"title"',
    '"severity"',
    '"file"',
    '"line"',
    '"whats_wrong"',
    '"why_it_matters"',
    '"how_to_fix"',
    '"acceptance_criteria"',
)
DIMENSION_MARKERS = {
    "review_correctness.md": ("logic", "edge", "data"),
    "review_maintainability.md": ("name", "comment", "style"),
    "review_scale.md": ("traffic", "timeout", "restart"),
    "review_security.md": ("unsafe", "private", "inject"),
}
REVIEWER_NAMES = (
    "review_correctness",
    "review_maintainability",
    "review_scale",
    "review_security",
)


def _agent_file(filename: str) -> Path:
    return AGENTS / Path(filename).stem / filename


def _tools(meta: AgentMeta) -> set[str]:
    tools = meta.tools
    if isinstance(tools, list):
        return set(tools)
    if isinstance(tools, str):
        return {part.strip() for part in tools.split(",")}
    return set()


def issue_blob_safe(issue: dict[str, object]) -> str:
    """Lowercased issue text for test mutations; mirrors the scorer."""
    return " ".join(str(value) for value in issue.values()).lower()


def _forbid_window(text: str, needle: str) -> str:
    at = text.find(needle)
    return text[max(0, at - 160) : at + 160]


def _assert_closes_own_playwright_cli_session(filename: str, text: str) -> None:
    """Webapp reviewers close only their named session, never host-wide close-all."""
    session = Path(filename).stem
    pin = f"-s={session}"
    named_open = f"npx playwright-cli {pin} open"
    named_close = f"npx playwright-cli {pin} close"
    assert named_open in text, filename
    assert named_close in text, filename
    assert "npx playwright-cli list" in text, filename
    lowered = text.lower()
    assert "empty" in lowered, filename
    tools = text.split("## Tools / privileges", 1)[1].split("## Anti-reward-hacking", 1)[0]
    blocked = text.split("## Blocked protocol", 1)[1].split("## Context acquisition", 1)[0]
    assert pin in tools, filename
    assert named_open in tools, filename
    assert named_close in tools, filename
    assert named_close in blocked, filename
    blocked_lower = blocked.lower()
    assert "close-all" not in blocked_lower, filename
    assert "kill-all" not in blocked_lower, filename
    tools_lower = tools.lower()
    for host_wide in ("close-all", "kill-all"):
        start = 0
        while True:
            at = tools_lower.find(host_wide, start)
            if at == -1:
                break
            window = tools_lower[max(0, at - 160) : at + 160]
            assert any(word in window for word in _FORBID_WORDS), filename
            start = at + len(host_wide)


def _assert_webapp_reviewer_forbids_secret_dump_and_off_origin(label: str, text: str) -> None:
    """Browser I/O must not dump session secrets or leave the local app origin."""
    lowered = text.lower()
    for command in _SECRET_DUMP_CLI:
        assert command in lowered, f"{label}: missing {command}"
    assert "request <n>" in lowered, label
    cookie_window = _forbid_window(lowered, "cookie-get")
    assert any(word in cookie_window for word in _FORBID_WORDS), label
    run_window = _forbid_window(lowered, "run-code")
    assert any(word in run_window for word in _FORBID_WORDS), label
    assert "eval" in run_window, label
    assert "storagestate" in lowered, label
    forbids_read = (
        "never `read`" in lowered
        or "never read" in lowered
        or ("never" in lowered and "`cat`" in lowered)
        or "do not read" in lowered
        or "do not `read`" in lowered
    )
    assert forbids_read, label
    assert "cookie or token" in lowered, label
    tools = text.split("## Tools / privileges", 1)[1].split("## Anti-reward-hacking", 1)[0].lower()
    assert "running local app origin" in tools, label
    assert "do not explore production" in tools, label
    assert "evaluate" in tools, label
    assert "cookie" in tools and "storage" in tools, label


def _assert_computer_use_stays_in_app_window(label: str, text: str) -> None:
    """computerUse may only observe the running local app window, not OS chrome."""
    tools = text.split("## Tools / privileges", 1)[1].split("## Anti-reward-hacking", 1)[0].lower()
    browser = " ".join(tools.split("**browser:**", 1)[1].split())
    assert "running local app window" in browser, label
    window_scope = _forbid_window(browser, "running local app window")
    assert "`computeruse`" in window_scope, label
    assert "ide" in window_scope, label
    assert "terminals" in window_scope, label
    assert "os chrome" in window_scope, label
    assert "password managers" in window_scope, label
    assert "devtools" in browser, label
    assert "application/storage/network" in browser, label
    assert "screenshot" in browser, label
    assert "authorization" in browser, label
    assert "secret-dump" in browser, label
    secret_dump = _forbid_window(browser, "secret-dump")
    assert "`computeruse`" in secret_dump, label
    assert "cookie" in secret_dump or "token" in secret_dump, label


ORCHESTRATOR_STAGE_TABLE_HEADER = "| Panel Review | Resolve Issues | Verifiers | Risk Classification | Merge |"
STARTED_COMMENT_HEADING = "**Started (fresh run only)**"
STARTED_SECTION_MARKER = "**Started (fresh run"
STARTED_COMMENT_PHRASE = "the pr review harness has started"
RESUME_STARTUP_MARKER = "**Resume startup (do not post Started)**"
RESOLVE_ISSUES_TEMPLATE_MARKER = "\n\n**Resolve Issues**\n\n````markdown"
QUEUED_STAGE_CELL = "⏳<br>queued"


def _fenced_markdown_after(text: str, marker: str) -> str:
    """Return the first ````markdown fence body after marker, or empty."""
    if marker not in text:
        return ""
    after = text.split(marker, 1)[1]
    fence = "````markdown"
    if fence not in after:
        return ""
    body = after.split(fence, 1)[1]
    closer = "````"
    if closer not in body:
        return ""
    return body.split(closer, 1)[0]


def _assert_orchestrator_github_comment_spec(text: str) -> None:
    """Option-G orchestrator PR comment contract: stage table, no alerts, merge outcomes."""
    lowered = text.lower()
    assert "### PR review harness" in text
    assert ORCHESTRATOR_STAGE_TABLE_HEADER in text
    assert "| Panel | Resolve | Verify | Risk | Merge |" not in text
    assert "one sentence per bullet" in lowered
    assert "<br>" in text
    assert "do not emit github alerts on orchestrator comments" in lowered
    # Decision-phase merge outcomes (all classifier terminal states)
    assert "Classifier `risk`" in text and "Classifier `merge`" in text
    assert "`blocked_by_protection`" in text
    assert "⛔<br>blocked" in text
    assert "⏸️<br>skipped" in text
    assert "✅<br>done" in text or "✅<br>merged" in text
    assert "⛔<br>token" not in text
    assert "reuse the classifier table labels verbatim" in lowered
    assert "https://cursor.com/agents/" in text
    assert "cursor cloud" in lowered
    assert "dashboard" in lowered
    # Abort comments must include this exact phrase.
    assert "pr review harness has aborted" in lowered
    started = _fenced_markdown_after(text, STARTED_SECTION_MARKER)
    assert STARTED_COMMENT_HEADING in text, "Started (fresh run only) heading missing"
    assert started, f"No Started template fence found after {STARTED_SECTION_MARKER!r}"
    assert STARTED_COMMENT_PHRASE in started.lower()
    assert ORCHESTRATOR_STAGE_TABLE_HEADER in started
    assert started.count(QUEUED_STAGE_CELL) == 5
    assert "all stages queued" in started.lower()
    assert "https://cursor.com/agents/" in started
    assert "cursor cloud dashboard for this harness" in started.lower()
    assert RESUME_STARTUP_MARKER in text


def _assert_risk_classifier_github_comment_spec(text: str) -> None:
    """Option-G risk_classifier PR comment contract: stage table, alerts, redacted errors."""
    lowered = text.lower()
    assert "### Risk classifier" in text
    assert "| Risk | Merge | Checks | Action |" in text
    assert "[!WARNING]" in text
    assert "[!CAUTION]" in text
    assert "<details>" in text
    assert "one sentence per bullet" in lowered
    assert "--body-file" in text
    assert "--edit-last" in text
    # WARNING only when checks green and merge blocked
    assert "merge blocked **and** required checks are green" in text
    assert "required checks pending or failing → no `[!WARNING]`" in text
    assert "Checks pending or failing" in text
    assert "table-only" in lowered
    assert "do not reuse the" in lowered and "merge-blocked" in lowered
    assert "while ci is red or pending" in lowered
    # Sanitized merge errors, not raw stderr
    assert "sanitized merge errors" in lowered
    assert "never paste raw credentials from `gh`" in lowered
    assert "stderr in pr comments" in lowered
    assert "redact tokens, pats, authorization headers" in lowered
    assert "post a short sanitized summary" in lowered
    assert "never paste verbatim" in lowered
    assert "post raw tokens, pats, or credentials from `gh` stderr" in lowered


def test_every_agent_file_is_classified() -> None:
    on_disk = {path.name for path in AGENTS.glob("*/*.md") if not path.name.startswith("_")}
    classified = (
        IMPLEMENTATION_AGENTS
        | REVIEW_DIMENSION_AGENTS
        | HARNESS_AGENTS
        | IMPLEMENTATION_HARNESS_AGENTS
        | {REVIEW_ORCHESTRATOR}
    )
    assert on_disk == classified
    assert (AGENTS / "_agent_template.md").is_file()


def test_base_loadout_does_not_include_dimensional_review_agents() -> None:
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    srcs = {entry["src"] for entry in loadout.agents}
    review_srcs = {f"agents/{Path(name).stem}/{name}" for name in REVIEW_DIMENSION_AGENTS | {REVIEW_ORCHESTRATOR}}
    assert srcs.isdisjoint(review_srcs)
    assert {entry["src"] for entry in loadout.mcps} >= {"mcps/context7", "mcps/linear"}
    assert "agents/davinci/davinci.md" in srcs
    assert "rules/core/colocated-evals.mdc" in {entry["src"] for entry in loadout.rules}


def test_pr_review_harness_loadout_includes_harness_agents_and_skills() -> None:
    loadout = load_loadout(REPO / "loadouts" / "pr_review_harness.yaml")
    srcs = {entry["src"] for entry in loadout.agents}
    expected_agents = {
        f"agents/{Path(name).stem}/{name}" for name in REVIEW_DIMENSION_AGENTS | HARNESS_AGENTS | {REVIEW_ORCHESTRATOR}
    }
    assert expected_agents <= srcs
    skill_srcs = {entry["src"] for entry in loadout.skills}
    assert skill_srcs == {
        "skills/dispatch-panel-review",
        "skills/dedupe-and-write-tasks",
        "skills/resolve-next-task",
        "skills/log-progress",
        "skills/dispatch-verifiers",
    }
    assert {entry["src"] for entry in loadout.rules} == {
        "rules/core/honor-check-intent.mdc",
    }


@pytest.mark.parametrize("filename", sorted(REVIEW_DIMENSION_AGENTS))
def test_dimension_reviewer_is_readonly_and_schema_complete(filename: str) -> None:
    path = _agent_file(filename)
    text = path.read_text()
    meta = parse_agent_md(path, text, file_stem=path.stem)
    assert meta.readonly is True
    tools = _tools(meta)
    assert REVIEW_TOOLS <= tools
    assert tools.isdisjoint(WRITE_TOOLS)
    for heading in REVIEW_HEADINGS:
        assert heading in text
    for field in ISSUE_SCHEMA_FIELDS:
        assert field in text
    assert "git push" in text.lower()
    assert "do not fix" in text.lower()
    lowered = text.lower()
    for marker in DIMENSION_MARKERS[filename]:
        assert marker in lowered


@pytest.mark.parametrize("filename", sorted(WEBAPP_REVIEW_AGENTS))
def test_webapp_reviewers_can_use_playwright_and_computer_use(filename: str) -> None:
    path = _agent_file(filename)
    text = path.read_text()
    meta = parse_agent_md(path, text, file_stem=path.stem)
    tools = _tools(meta)
    assert meta.readonly is True
    assert WEBAPP_REVIEW_TOOLS <= tools
    assert "Task" not in tools
    assert tools.isdisjoint(WRITE_TOOLS)
    assert "mcp__playwright" not in tools
    assert "mcp__playwright" not in text
    assert "@playwright/mcp" not in text
    lowered = text.lower()
    assert "`computeruse`" in lowered
    assert "`task`" not in lowered
    assert "npx playwright-cli" in lowered
    assert "`playwright` loadout" in lowered
    assert "stop immediately" in lowered
    assert "retrying `open`" in lowered
    assert "call `computeruse` directly" in lowered
    blocked = text.split("## Blocked protocol", 1)[1].split("## Context acquisition", 1)[0].lower()
    assert "stop immediately" in blocked
    assert "retrying `open`" in blocked
    assert "playwright mcp is absent" not in blocked
    assert "spawning another `computeruse`" not in blocked
    assert "calling `computeruse` again" in blocked
    stop_sentence = next(part for part in blocked.replace("\n", " ").split(".") if "stop immediately" in part)
    assert "mcp" not in stop_sentence
    if filename == VERIFIER:
        assert "check ui claims against a running webapp" in lowered
    else:
        assert "observe a running webapp" in lowered
    _assert_closes_own_playwright_cli_session(filename, text)
    if filename == VERIFIER:
        assert "continue remaining" in lowered
    _assert_webapp_reviewer_forbids_secret_dump_and_off_origin(filename, text)
    _assert_computer_use_stays_in_app_window(filename, text)


def test_orchestrator_dispatches_four_reviewers_and_groups_tasks() -> None:
    path = _agent_file(REVIEW_ORCHESTRATOR)
    text = path.read_text()
    meta = parse_agent_md(path, text, file_stem=path.stem)
    assert meta.readonly is not True
    tools = _tools(meta)
    assert REVIEW_TOOLS <= tools
    assert "Write" in tools
    for heading in REVIEW_HEADINGS:
        assert heading in text
    lowered = text.lower()
    for name in REVIEWER_NAMES:
        assert name in text
    assert "parallel" in lowered
    assert "1-3" in lowered or "1–3" in lowered
    assert "dropped_duplicates" in text
    assert '"tasks"' in text
    assert "TASKS_TO_RESOLVE.md" in text
    assert "issue_resolver" in lowered
    assert "risk_classifier" in lowered
    assert "git push" in lowered
    assert "do not implement" in lowered
    assert "gh pr merge" in lowered
    assert "do not merge" in lowered or "no `gh pr merge`" in lowered or "no gh pr merge" in lowered


def test_orchestrator_hashes_and_deletes_the_tasks_file() -> None:
    text = _agent_file(REVIEW_ORCHESTRATOR).read_text()
    lowered = text.lower()
    assert "git rev-parse --short" in text
    assert "TASKS_TO_RESOLVE-<" in text
    assert "headrefoid" in lowered or "head_ref_oid" in lowered or "head sha" in lowered
    assert "delete" in lowered and "before" in lowered and "exit" in lowered
    assert "never write unhashed" in lowered or "do not write unhashed" in lowered


def test_orchestrator_stale_cleanup_compares_embedded_sha_not_md_suffix() -> None:
    text = _agent_file(REVIEW_ORCHESTRATOR).read_text()
    lowered = text.lower()
    assert "whose suffix does not equal" not in lowered
    assert "between `tasks_to_resolve-` and `.md`" in lowered
    assert "other-sha" in lowered
    assert "never delete" in lowered and "[open]" in text
    assert "keep `tasks_path` for the whole run" in lowered


def test_orchestrator_resume_skips_panel_when_open_manifest_present() -> None:
    text = _agent_file(REVIEW_ORCHESTRATOR).read_text()
    lowered = text.lower()
    assert "resume" in lowered
    assert "freeze" in lowered or "frozen" in lowered
    assert "skip" in lowered and "dispatch-panel-review" in text
    assert "[open]" in text
    assert "tasks_path" in text
    assert "do not run dedupe until the manifest is fully" in lowered
    assert "resolved" in lowered


def test_orchestrator_trims_review_history_after_other_tasks() -> None:
    source = _agent_file(REVIEW_ORCHESTRATOR).read_text()
    vendored = (REPO / ".claude" / "agents" / "review_orchestrator.md").read_text()
    for text in (source, vendored):
        lowered = text.lower()
        assert "REVIEW_HISTORY.md" in text
        assert "30 days" in lowered
        assert "trim" in lowered
        assert "trim_review_history.py" in text
        definition = text.split("## Definition of done", 1)[1].split("## Tools / privileges", 1)[0]
        step7 = definition.split("7. ", 1)[1]
        assert "after all other tasks" in step7.lower()
        assert "30 days" in step7.lower()
        invoked = text.split("### When invoked", 1)[1].split("## Output schema", 1)[0].lower()
        assert invoked.find("trim") > invoked.find("risk_classifier")
        anti = text.split("## Anti-reward-hacking", 1)[1].split("## Blocked protocol", 1)[0].lower()
        assert "30 days" in anti or "30-day" in anti
        assert "during panel" in anti or "during the panel" in anti


def test_orchestrator_exit_delete_uses_frozen_tasks_path_on_resume() -> None:
    text = _agent_file(REVIEW_ORCHESTRATOR).read_text()
    lowered = text.lower()
    definition = text.split("## Definition of done", 1)[1].split("## Tools / privileges", 1)[0]
    step6 = definition.split("6. ", 1)[1].split("\n7.", 1)[0]
    assert "frozen `tasks_path`" in step6.lower()
    assert "delete `tasks_to_resolve-<short-sha>.md` if it" not in step6.lower()
    assert "do not delete from pr-head sha alone" in step6.lower()
    assert "frozen `<short-sha>`" in lowered
    blocked = text.split("## Blocked protocol", 1)[1].split("## Context acquisition", 1)[0]
    assert "frozen `tasks_path`" in blocked.lower()
    when_invoked = text.split("### When invoked", 1)[1].split("## Output schema", 1)[0]
    assert "frozen `tasks_path`" in when_invoked.lower()
    assert "orphans the real" in lowered
    text = _agent_file(REVIEW_ORCHESTRATOR).read_text()
    lowered = text.lower()
    assert "github" in lowered and "pull request" in lowered
    assert "gh pr comment" in lowered
    assert "--edit-last" in lowered
    assert "each run creates its own" in lowered
    assert "github_comment_url" in text
    assert "inputs.github_pr" in text or '"github_pr"' in text


def test_orchestrator_github_comments_use_stage_table_and_bullets() -> None:
    _assert_orchestrator_github_comment_spec(_agent_file(REVIEW_ORCHESTRATOR).read_text())


def test_orchestrator_posts_start_comment_as_soon_as_it_begins() -> None:
    source = _agent_file(REVIEW_ORCHESTRATOR).read_text()
    vendored = (REPO / ".claude" / "agents" / "review_orchestrator.md").read_text()
    for text in (source, vendored):
        lowered = text.lower()
        comments = text.split("### GitHub PR comments", 1)[1].split("### When invoked", 1)[0].lower()
        assert "as soon as" in comments
        assert "run-info" in comments
        assert "never invent" in comments
        definition = text.split("## Definition of done", 1)[1].split("## Tools / privileges", 1)[0]
        step2 = definition.split("2. ", 1)[1].split("\n3.", 1)[0].lower()
        assert "started" in step2
        assert "as soon as" in step2
        started_at = step2.find("started")
        sha_markers = [step2.find(marker) for marker in ("rev-parse", "headrefoid")]
        sha_at = min(pos for pos in sha_markers if pos != -1)
        assert started_at != -1
        assert sha_at != -1
        assert started_at < sha_at
        context = text.split("## Context acquisition", 1)[1].split("## Repo conventions", 1)[0].lower()
        context_started_at = context.find("started")
        context_diff_at = context.find("gh pr diff")
        assert context_started_at != -1
        assert context_diff_at != -1
        assert context_started_at < context_diff_at
        invoked = text.split("### When invoked", 1)[1].split("## Output schema", 1)[0].lower()
        started_at = invoked.find("started")
        review_at = invoked.find("**review**")
        assert started_at != -1
        assert review_at != -1
        assert started_at < review_at
        anti = text.split("## Anti-reward-hacking", 1)[1].split("## Blocked protocol", 1)[0].lower()
        assert "started" in anti
        assert "invent" in anti and "dashboard" in anti
        assert "skip" in anti
        assert "exactly once" in anti
        assert "fresh startup" in anti or "fresh run" in anti
        assert "github_comment_url" in text
        assert "gh pr comment" in lowered


def test_orchestrator_started_comment_reflects_resume_state() -> None:
    """Fresh runs post all-queued Started; resume runs skip Started and show Panel completed."""
    source = _agent_file(REVIEW_ORCHESTRATOR).read_text()
    vendored = (REPO / ".claude" / "agents" / "review_orchestrator.md").read_text()
    for text in (source, vendored):
        lowered = text.lower()
        started_fresh = _fenced_markdown_after(text, STARTED_SECTION_MARKER)
        assert started_fresh.count(QUEUED_STAGE_CELL) == 5
        assert "all stages queued" in started_fresh.lower()
        assert RESUME_STARTUP_MARKER in text
        assert "do not post started" in RESUME_STARTUP_MARKER.lower()
        resume_section = text.split(RESUME_STARTUP_MARKER, 1)[1].split("**Panel Review**", 1)[0]
        resume_lower = resume_section.lower()
        assert "skip started" in resume_lower
        assert "panel review" in resume_lower
        assert "completed" in resume_lower or "✅" in resume_section
        assert "queued" in resume_lower and "not queued" in resume_lower
        definition = text.split("## Definition of done", 1)[1].split("## Tools / privileges", 1)[0]
        step2 = definition.split("2. ", 1)[1].split("\n3.", 1)[0].lower()
        assert "resume detection" in step2
        assert "do not post started" in step2
        assert "resolve issues" in step2
        assert "fresh startup" in step2
        comments = text.split("### GitHub PR comments", 1)[1].split("### When invoked", 1)[0].lower()
        assert "fresh run" in comments and "resume run" in comments
        assert "skip started" in comments
        invoked = text.split("### When invoked", 1)[1].split("## Output schema", 1)[0].lower()
        assert "skip started" in invoked
        assert "resolve issues" in invoked
        assert "panel review completed" in invoked or "panel review" in invoked
        anti = text.split("## Anti-reward-hacking", 1)[1].split("## Blocked protocol", 1)[0].lower()
        assert "resume run" in anti and "started" in anti
        assert RESOLVE_ISSUES_TEMPLATE_MARKER in text
        resolve_body = text.split(RESOLVE_ISSUES_TEMPLATE_MARKER, 1)[1]
        resolve_template = resolve_body.split("````", 1)[0]
        assert "✅" in resolve_template
        assert "🔄" in resolve_template or "task-00" in resolve_template.lower()


def test_orchestrator_aborts_when_the_pull_request_is_merged() -> None:
    source = _agent_file(REVIEW_ORCHESTRATOR).read_text()
    vendored = (REPO / ".claude" / "agents" / "review_orchestrator.md").read_text()
    for text in (source, vendored):
        lowered = text.lower()
        assert "gh pr view" in lowered
        assert "merged" in lowered
        assert "abort" in lowered
        assert "do not commit" in lowered or "don't commit" in lowered
        assert "issue_resolver" in lowered
        assert "/archive" in text
        assert "cloudAgentBcId" in text or "cloudagentbcid" in lowered
        assert '"aborted"' in text
        assert "phase" in lowered and "abort" in lowered
        anti = text.split("## Anti-reward-hacking", 1)[1].split("## Blocked protocol", 1)[0].lower()
        assert "merged" in anti
        invoked = text.split("### When invoked", 1)[1].split("## Output schema", 1)[0].lower()
        assert "merged" in invoked
        assert "abort" in invoked


def test_risk_classifier_github_comments_use_stage_table_with_human_action_alerts() -> None:
    _assert_risk_classifier_github_comment_spec(_agent_file(RISK_CLASSIFIER).read_text())


def test_vendored_harness_agents_match_github_comment_stage_table_contract() -> None:
    claude = REPO / ".claude" / "agents"
    _assert_orchestrator_github_comment_spec((claude / "review_orchestrator.md").read_text())
    _assert_risk_classifier_github_comment_spec((claude / "risk_classifier.md").read_text())


def test_orchestrator_does_not_use_linear_as_artifact_rally_point() -> None:
    text = _agent_file(REVIEW_ORCHESTRATOR).read_text().lower()
    assert "rally point" not in text
    assert "prepare_attachment_upload" not in text
    assert "linear_issue" not in text
    loadout = load_loadout(REPO / "loadouts" / "base.yaml")
    assert any(entry["src"] == "mcps/linear" for entry in loadout.mcps)


def test_dimension_reviewers_do_not_write_harness_files() -> None:
    for filename in REVIEW_DIMENSION_AGENTS:
        text = _agent_file(filename).read_text().lower()
        assert "do not write files" in text
        assert "tasks_to_resolve.md" in text
        assert "rally point" not in text


def test_evals_json_files_exist_and_cover_each_review_agent() -> None:
    suite = load_evals()
    agents = {entry["agent"] for entry in suite["evals"]}
    assert agents == set(REVIEW_AGENTS)
    for entry in suite["evals"]:
        if entry["agent"] == "review_orchestrator":
            assert entry["expected_groups"]
        else:
            assert entry["must_find"]
        agent_root = AGENTS_DIR / entry["agent"]
        for relative in entry["files"]:
            assert (agent_root / relative).is_file(), relative


@pytest.mark.parametrize(
    "eval_id",
    [
        "review-correctness-order-service",
        "review-maintainability-report-builder",
        "review-scale-fanout-worker",
        "review-security-user-api",
    ],
)
def test_golden_dimension_report_passes_eval(eval_id: str) -> None:
    spec = eval_by_id(eval_id)
    report = load_golden(spec["agent"])
    result = score_dimension_report(report, spec)
    assert result.ok, result.failures


@pytest.mark.parametrize("agent", list(REVIEW_AGENTS))
def test_blank_agent_transcript_fails_behavior_score(agent: str) -> None:
    spec = next(entry for entry in load_evals()["evals"] if entry["agent"] == agent)
    report = load_blank_run(agent)
    result = score_behavior(report, spec)
    assert not result.ok, f"blank agent unexpectedly passed {spec['id']}"


def test_golden_harness_reports_pass_eval() -> None:
    spec = eval_by_id("issue-resolver-tax-after-discount")
    assert score_blob_report(load_golden("issue_resolver"), spec).ok
    spec = eval_by_id("risk-classifier-typo-squash")
    assert score_blob_report(load_golden("risk_classifier"), spec).ok
    spec = eval_by_id("verifier-debugger-claim-false")
    result = score_dimension_report(load_golden("verifier"), spec)
    assert result.ok, result.failures
    spec = eval_by_id("review-orchestrator-group-findings")
    result = score_orchestrator_report(load_golden("review_orchestrator"), spec)
    assert result.ok, result.failures


def test_dimension_scorer_fails_when_a_must_find_is_removed() -> None:
    spec = eval_by_id("review-correctness-order-service")
    report = load_golden("review_correctness")
    report["issues"] = [issue for issue in report["issues"] if "pop" not in issue_blob_safe(issue)]
    result = score_dimension_report(report, spec)
    assert not result.ok
    assert any("caller-mutation" in failure for failure in result.failures)


def test_dimension_scorer_fails_when_out_of_scope_issue_is_filed() -> None:
    spec = eval_by_id("review-correctness-order-service")
    report = load_golden("review_correctness")
    report["issues"].append(
        {
            "id": "C-999",
            "title": "Rename _tmp",
            "severity": "minor",
            "file": "files/correctness/order_service.py",
            "line": 32,
            "symbol": "_tmp",
            "whats_wrong": "poor comment and rename _tmp to something clearer",
            "why_it_matters": "style",
            "how_to_fix": ["rename _tmp"],
            "acceptance_criteria": ["renamed"],
            "suggested_test": "none",
            "do_not_change": "apply_line_items",
        }
    )
    result = score_dimension_report(report, spec)
    assert not result.ok
    assert any("naming-nit" in failure for failure in result.failures)


def test_orchestrator_scorer_rejects_more_than_three_issues_in_a_task() -> None:
    spec = eval_by_id("review-orchestrator-group-findings")
    report = load_golden("review_orchestrator")
    report["tasks"] = [
        {
            "id": "TASK-001",
            "title": "everything",
            "path": "TASKS_TO_RESOLVE-abc1234.md",
            "issue_ids": ["SEC-001", "SEC-002", "SEC-003", "C-001"],
        }
    ]
    result = score_orchestrator_report(report, spec)
    assert not result.ok
    assert any("4 issues" in failure or "groups" in failure for failure in result.failures)


def test_orchestrator_scorer_rejects_keeping_a_known_duplicate() -> None:
    spec = eval_by_id("review-orchestrator-group-findings")
    report = load_golden("review_orchestrator")
    report["dropped_duplicates"] = []
    result = score_orchestrator_report(report, spec)
    assert not result.ok
    assert any("dropped_duplicates" in failure for failure in result.failures)


def test_parse_report_reads_fenced_json() -> None:
    report = parse_report('intro\n```json\n{"status": "ok", "agent": "review_correctness"}\n```\n')
    assert report["agent"] == "review_correctness"


def test_evals_path_is_the_committed_suite() -> None:
    for agent in REVIEW_AGENTS:
        path = evals_path(agent)
        assert path.is_file(), path
        raw = json.loads(path.read_text())
        assert raw["agent"] == agent
        assert (evals_root(agent) / "goldens" / f"{agent}.json").is_file()
    assert load_evals()["suite"] == "dimensional-review-agents"


def test_verifier_is_readonly_and_judges_claims() -> None:
    text = _agent_file(VERIFIER).read_text()
    meta = parse_agent_md(_agent_file(VERIFIER), text, file_stem="verifier")
    assert meta.readonly is True
    assert _tools(meta).isdisjoint(WRITE_TOOLS)
    lowered = text.lower()
    assert "verifiers.md" in lowered
    assert "true" in lowered and "false" in lowered
    assert "missing" in lowered
    assert "do not create" in lowered or "never create" in lowered


def test_issue_resolver_pushes_and_does_not_merge() -> None:
    text = _agent_file(ISSUE_RESOLVER).read_text().lower()
    assert "git push" in text
    assert "gh pr merge" in text
    assert "do not merge" in text
    assert "tasks_to_resolve-" in text
    assert "do not delete" in text or "never delete" in text


def test_issue_resolver_eval_uses_hashed_tasks_fixture() -> None:
    suite = load_evals()
    entry = next(item for item in suite["evals"] if item["agent"] == "issue_resolver")
    prompt = entry["prompt"]
    assert "tasks_path" in prompt.lower()
    assert "TASKS_TO_RESOLVE-" in prompt
    assert all("TASKS_TO_RESOLVE-" in relative for relative in entry["files"] if "TASKS_TO_RESOLVE" in relative)
    assert not any(relative.endswith("/TASKS_TO_RESOLVE.md") for relative in entry["files"])


def test_risk_classifier_squash_merges_without_admin() -> None:
    text = _agent_file(RISK_CLASSIFIER).read_text().lower()
    assert "gh pr merge" in text
    assert "--squash" in text
    assert "--admin" in text
    assert "never" in text
    assert "required checks" in text
    assert "low risk" in text or "low-risk" in text
