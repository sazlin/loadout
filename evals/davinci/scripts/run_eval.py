#!/usr/bin/env python3
"""Run davinci evals: copy fixtures, invoke davinci, score with LLM judges.

Supports local `cursor-agent` (flaky streaming) and Cursor Cloud Agents API
(`--runtime cloud`, requires `CURSOR_API_KEY`).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_ROOT = REPO_ROOT / "evals" / "davinci"
FILES_DIR = EVAL_ROOT / "files"
WORKSPACE_DIR = EVAL_ROOT / "workspace"
RESULTS_DIR = EVAL_ROOT / "results"
DAVINCI_AGENT = REPO_ROOT / "agents" / "davinci.md"
JUDGE_RUBRIC = EVAL_ROOT / "references" / "judge-rubric.md"
EVALS_JSON = EVAL_ROOT / "evals.json"

DAVINCI_MODEL = "composer-2.5"
JUDGE_MODELS_LOCAL = ("cursor-grok-4.5-high", "cursor-grok-4.6-high")
JUDGE_MODELS_CLOUD = ("grok-4.5", "grok-4.6")
CLOUD_API = "https://api.cursor.com/v1"
DEFAULT_REPO_URL = "https://github.com/sazlin/loadout"


@dataclass(frozen=True)
class EvalCase:
    id: int
    name: str
    prompt: str
    source_file: str
    expectations: list[str]


def judge_models_for(runtime: str) -> tuple[str, ...]:
    return JUDGE_MODELS_CLOUD if runtime == "cloud" else JUDGE_MODELS_LOCAL


def load_evals() -> list[EvalCase]:
    data = json.loads(EVALS_JSON.read_text())
    cases: list[EvalCase] = []
    for entry in data["evals"]:
        rel = entry["files"][0].removeprefix("evals/files/")
        cases.append(
            EvalCase(
                id=entry["id"],
                name=entry["name"],
                prompt=entry["prompt"],
                source_file=rel,
                expectations=entry.get("expectations", []),
            )
        )
    return cases


def reset_workspace(case: EvalCase) -> Path:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    for stale in WORKSPACE_DIR.glob("*.py"):
        stale.unlink()
    dest = WORKSPACE_DIR / case.source_file
    shutil.copy2(FILES_DIR / case.source_file, dest)
    return dest


def run_python(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def run_cursor_agent_local(
    *,
    model: str,
    prompt: str,
    timeout_s: int,
) -> str:
    cmd = [
        "cursor-agent",
        "--print",
        "--output-format",
        "text",
        "--model",
        model,
        "--force",
        "--trust",
        "--workspace",
        str(REPO_ROOT),
        prompt,
    ]
    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_s,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"cursor-agent failed (model={model}, code={completed.returncode}): "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed.stdout


class CloudAgentsClient:
    """Minimal Cloud Agents API client (Basic auth with API key)."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key.strip()
        if not self.api_key:
            raise RuntimeError("CURSOR_API_KEY is empty")

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        timeout_s: int = 180,
    ) -> dict[str, object]:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            f"{CLOUD_API}{path}",
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        token = base64.b64encode(f"{self.api_key}:".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"cloud API {method} {path} -> {exc.code}: {detail}") from exc
        return json.loads(raw) if raw else {}

    def create_agent(
        self,
        *,
        prompt: str,
        model: str,
        name: str,
        repo_url: str | None,
        starting_ref: str | None,
        no_repo: bool,
    ) -> tuple[str, str, dict[str, object]]:
        body: dict[str, object] = {
            "prompt": {"text": prompt},
            "model": {"id": model},
            "name": name[:100],
            "autoCreatePR": False,
            "skipReviewerRequest": True,
        }
        if not no_repo and repo_url:
            repo: dict[str, object] = {"url": repo_url}
            if starting_ref:
                repo["startingRef"] = starting_ref
            body["repos"] = [repo]
            body["workOnCurrentBranch"] = False
        payload = self._request("POST", "/agents", body=body, timeout_s=300)
        agent = payload.get("agent")
        run = payload.get("run")
        if not isinstance(agent, dict) or not isinstance(run, dict):
            raise TypeError(f"unexpected create response: {payload}")
        agent_id = str(agent["id"])
        run_id = str(run["id"])
        return agent_id, run_id, run

    def get_run(self, agent_id: str, run_id: str) -> dict[str, object]:
        return self._request("GET", f"/agents/{agent_id}/runs/{run_id}", timeout_s=60)

    def wait_for_run(
        self,
        agent_id: str,
        run_id: str,
        *,
        timeout_s: int,
        poll_s: float = 5.0,
        seed: dict[str, object] | None = None,
    ) -> dict[str, object]:
        deadline = time.time() + timeout_s
        terminal = {"FINISHED", "ERROR", "CANCELLED", "EXPIRED"}
        last: dict[str, object] = dict(seed or {})
        if str(last.get("status", "")) in terminal:
            # Create often blocks until the first run finishes; fetch full record for result text.
            last = self.get_run(agent_id, run_id)
            if str(last.get("status", "")) != "FINISHED":
                raise RuntimeError(f"cloud run ended {last.get('status')}: {last}")
            return last
        while time.time() < deadline:
            last = self.get_run(agent_id, run_id)
            status = str(last.get("status", ""))
            print(f"  cloud run {run_id} status={status}", flush=True)
            if status in terminal:
                if status != "FINISHED":
                    raise RuntimeError(f"cloud run ended {status}: {last}")
                return last
            time.sleep(poll_s)
        raise TimeoutError(f"cloud run {run_id} timed out after {timeout_s}s; last={last}")

    def run_prompt(
        self,
        *,
        prompt: str,
        model: str,
        name: str,
        timeout_s: int,
        repo_url: str | None,
        starting_ref: str | None,
        no_repo: bool,
    ) -> dict[str, object]:
        agent_id, run_id, seed = self.create_agent(
            prompt=prompt,
            model=model,
            name=name,
            repo_url=repo_url,
            starting_ref=starting_ref,
            no_repo=no_repo,
        )
        print(f"  cloud agent={agent_id} run={run_id} model={model}", flush=True)
        print(f"  url=https://cursor.com/agents/{agent_id}", flush=True)
        print(f"  create_status={seed.get('status')}", flush=True)
        result = self.wait_for_run(agent_id, run_id, timeout_s=timeout_s, seed=seed)
        result["_agent_id"] = agent_id
        result["_run_id"] = run_id
        return result


def extract_python_fence(text: str) -> str | None:
    match = re.search(r"```python\n([\s\S]*?)```", text)
    if match:
        return match.group(1).strip() + "\n"
    match = re.search(r"```\n([\s\S]*?)```", text)
    if match and ("def " in match.group(1) or "class " in match.group(1)):
        return match.group(1).strip() + "\n"
    return None


def build_davinci_prompt_local(case: EvalCase, target: Path) -> str:
    rel_target = target.relative_to(REPO_ROOT).as_posix()
    expectations = "\n".join(f"- {item}" for item in case.expectations)
    return (
        f"Follow the davinci agent charter in `{DAVINCI_AGENT.relative_to(REPO_ROOT)}`.\n\n"
        f"Simplify `{rel_target}` by removing AI code smells without changing behavior.\n\n"
        f"Expectations:\n{expectations}\n\n"
        f"After edits, run: `python {rel_target}`\n"
        "Do not modify tests or assertions. Do not add new files."
    )


def build_davinci_prompt_cloud(case: EvalCase, source: str) -> str:
    charter = DAVINCI_AGENT.read_text()
    expectations = "\n".join(f"- {item}" for item in case.expectations)
    return (
        "You are running as the davinci code-simplification agent on a Cursor Cloud VM.\n\n"
        "Follow this charter exactly:\n"
        f"---- CHARTER (agents/davinci.md) ----\n{charter}\n---- END CHARTER ----\n\n"
        f"Create `/tmp/{case.source_file}` with the ORIGINAL source below, then simplify that file "
        "in place (remove AI smells, preserve behavior).\n\n"
        f"Expectations:\n{expectations}\n\n"
        f"After edits, run: `python /tmp/{case.source_file}` and fix until it passes.\n"
        "Finally, respond with the COMPLETE simplified file inside a single ```python fenced block. "
        "No other prose after the fence.\n\n"
        f"---- ORIGINAL SOURCE ----\n```python\n{source}\n```\n"
    )


def build_judge_prompt(*, original: str, simplified: str, expectations: list[str]) -> str:
    rubric = JUDGE_RUBRIC.read_text()
    expectation_block = "\n".join(f"- {item}" for item in expectations)
    return (
        f"{rubric}\n\n"
        "## Expectations\n"
        f"{expectation_block}\n\n"
        "## Original\n"
        f"```python\n{original}\n```\n\n"
        "## Simplified\n"
        f"```python\n{simplified}\n```\n"
    )


def parse_judge_json(text: str) -> dict[str, object]:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError(f"no JSON object in judge response: {text[:500]}")
    return json.loads(match.group())


def mean_overall(judge_results: dict[str, object]) -> float | None:
    scores: list[float] = []
    for payload in judge_results.values():
        if not isinstance(payload, dict):
            continue
        parsed = payload.get("parsed")
        if isinstance(parsed, dict) and isinstance(parsed.get("overall"), (int, float)):
            scores.append(float(parsed["overall"]))
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def dry_run_case(case: EvalCase) -> dict[str, object]:
    target = reset_workspace(case)
    baseline = run_python(target)
    return {
        "eval_id": case.id,
        "name": case.name,
        "baseline_passed": baseline.returncode == 0,
        "baseline_stdout": baseline.stdout.strip(),
        "workspace_file": target.relative_to(REPO_ROOT).as_posix(),
        "lines_before": len(target.read_text().splitlines()),
        "dry_run": True,
    }


def run_case(
    case: EvalCase,
    *,
    runtime: str,
    cloud: CloudAgentsClient | None,
    repo_url: str | None,
    starting_ref: str | None,
    no_repo: bool,
    judge_models: tuple[str, ...],
    davinci_timeout_s: int,
    judge_timeout_s: int,
    skip_davinci: bool,
    dry_run: bool,
) -> dict[str, object]:
    if dry_run:
        return dry_run_case(case)

    target = reset_workspace(case)
    baseline = run_python(target)
    if baseline.returncode != 0:
        raise RuntimeError(f"baseline failed for {case.name}: {baseline.stderr}")

    original_source = target.read_text()
    davinci_output = ""
    cloud_meta: dict[str, object] = {}

    if not skip_davinci:
        if runtime == "cloud":
            assert cloud is not None
            run = cloud.run_prompt(
                prompt=build_davinci_prompt_cloud(case, original_source),
                model=DAVINCI_MODEL,
                name=f"davinci:{case.name}",
                timeout_s=davinci_timeout_s,
                repo_url=repo_url,
                starting_ref=starting_ref,
                no_repo=no_repo,
            )
            davinci_output = str(run.get("result") or "")
            cloud_meta["davinci"] = {
                "agent_id": run.get("_agent_id"),
                "run_id": run.get("_run_id"),
                "url": f"https://cursor.com/agents/{run.get('_agent_id')}",
            }
            simplified = extract_python_fence(davinci_output)
            if not simplified:
                raise RuntimeError(f"cloud davinci returned no python fence for {case.name}: {davinci_output[:800]}")
            target.write_text(simplified)
        else:
            davinci_output = run_cursor_agent_local(
                model=DAVINCI_MODEL,
                prompt=build_davinci_prompt_local(case, target),
                timeout_s=davinci_timeout_s,
            )

    post_run = run_python(target)
    simplified_source = target.read_text()

    judge_results: dict[str, object] = {}
    for model in judge_models:
        judge_prompt = build_judge_prompt(
            original=original_source,
            simplified=simplified_source,
            expectations=case.expectations,
        )
        if runtime == "cloud":
            assert cloud is not None
            run = cloud.run_prompt(
                prompt=judge_prompt + "\nRespond with ONLY the JSON object from the rubric.",
                model=model,
                name=f"judge:{case.name}:{model}",
                timeout_s=judge_timeout_s,
                repo_url=repo_url,
                starting_ref=starting_ref,
                no_repo=True,  # judges are pure scoring; no repo needed
            )
            judge_text = str(run.get("result") or "")
            judges_meta = cloud_meta.setdefault("judges", {})
            assert isinstance(judges_meta, dict)
            judges_meta[model] = {
                "agent_id": run.get("_agent_id"),
                "run_id": run.get("_run_id"),
                "url": f"https://cursor.com/agents/{run.get('_agent_id')}",
            }
        else:
            judge_text = run_cursor_agent_local(
                model=model,
                prompt=judge_prompt,
                timeout_s=judge_timeout_s,
            )
        judge_results[model] = {
            "raw": judge_text,
            "parsed": parse_judge_json(judge_text),
        }

    snapshot_dir = RESULTS_DIR / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / f"{case.name}.before.py").write_text(original_source)
    (snapshot_dir / f"{case.name}.after.py").write_text(simplified_source)

    return {
        "eval_id": case.id,
        "name": case.name,
        "runtime": runtime,
        "baseline_passed": baseline.returncode == 0,
        "post_davinci_passed": post_run.returncode == 0,
        "post_davinci_stderr": post_run.stderr,
        "lines_before": len(original_source.splitlines()),
        "lines_after": len(simplified_source.splitlines()),
        "davinci_model": DAVINCI_MODEL,
        "judge_models": list(judge_models),
        "judge_results": judge_results,
        "mean_overall": mean_overall(judge_results),
        "davinci_output_excerpt": davinci_output[:2000],
        "cloud": cloud_meta,
        "skipped_davinci": skip_davinci,
    }


def write_results(payload: dict[str, object]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"run-{stamp}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def resolve_starting_ref(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    completed = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return completed.stdout.strip() or None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval", type=int, help="Run a single eval id")
    parser.add_argument("--skip-davinci", action="store_true", help="Only reset fixtures and run judges")
    parser.add_argument("--dry-run", action="store_true", help="Validate fixtures/workspace without agents")
    parser.add_argument(
        "--runtime",
        choices=("local", "cloud"),
        default="cloud",
        help="Agent runtime (default: cloud)",
    )
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="GitHub repo URL for cloud agents")
    parser.add_argument("--starting-ref", default=None, help="Branch/SHA for cloud repo clone")
    parser.add_argument(
        "--no-repo",
        action="store_true",
        help="Launch cloud agents without cloning a repo (prompt-embedded sources)",
    )
    parser.add_argument("--davinci-timeout", type=int, default=900)
    parser.add_argument("--judge-timeout", type=int, default=600)
    args = parser.parse_args()

    cases = load_evals()
    if args.eval is not None:
        cases = [case for case in cases if case.id == args.eval]
        if not cases:
            print(f"unknown eval id: {args.eval}", file=sys.stderr)
            return 2

    cloud: CloudAgentsClient | None = None
    if args.runtime == "cloud" and not args.dry_run:
        api_key = os.environ.get("CURSOR_API_KEY", "")
        if not api_key:
            print(
                "CURSOR_API_KEY is required for --runtime cloud.\n"
                "Create one at https://cursor.com/dashboard/api and export it:\n"
                '  export CURSOR_API_KEY="key_..."',
                file=sys.stderr,
            )
            return 2
        cloud = CloudAgentsClient(api_key)

    starting_ref = None if args.no_repo else resolve_starting_ref(args.starting_ref)
    judge_models = judge_models_for(args.runtime)

    run_payload: dict[str, object] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "runtime": args.runtime,
        "davinci_model": DAVINCI_MODEL,
        "judge_models": list(judge_models),
        "repo_url": None if args.no_repo else args.repo_url,
        "starting_ref": starting_ref,
        "cases": [],
    }

    for case in cases:
        print(f"Running eval {case.id}: {case.name} (runtime={args.runtime})", flush=True)
        result = run_case(
            case,
            runtime=args.runtime,
            cloud=cloud,
            repo_url=None if args.no_repo else args.repo_url,
            starting_ref=starting_ref,
            no_repo=args.no_repo or args.runtime != "cloud",
            judge_models=judge_models,
            davinci_timeout_s=args.davinci_timeout,
            judge_timeout_s=args.judge_timeout,
            skip_davinci=args.skip_davinci,
            dry_run=args.dry_run,
        )
        run_payload["cases"].append(result)
        print(json.dumps(result, indent=2))

    if not args.dry_run:
        overalls = [
            float(case["mean_overall"])
            for case in run_payload["cases"]
            if isinstance(case, dict) and isinstance(case.get("mean_overall"), (int, float))
        ]
        run_payload["suite_mean_overall"] = round(sum(overalls) / len(overalls), 2) if overalls else None

    out_path = write_results(run_payload)
    print(f"Wrote {out_path}")
    if run_payload.get("suite_mean_overall") is not None:
        print(f"suite_mean_overall={run_payload['suite_mean_overall']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
