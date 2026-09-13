#!/usr/bin/env python3
"""
inspect_repo.py: gather the facts a README needs, from the repo itself.

Usage:
    python3 inspect_repo.py [REPO_PATH] [--json]

Prints a fact sheet: identity, install commands, entry points, license, CI,
docs, assets, community links, and what the existing README is missing.
Read-only. Standard library only. Never guesses: unknown fields are reported
as null so the agent knows to ask instead of invent.
"""

import json
import os
import re
import subprocess
import sys

SKIP_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "target",
    "vendor",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    ".cache",
    "site-packages",
    ".tox",
}


def sh(cmd, cwd):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=15, check=False).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def read(path, limit=200000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


def walk(root, max_files=6000):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and d != ".git"]
        for fn in filenames:
            out.append(os.path.relpath(os.path.join(dirpath, fn), root))
            if len(out) >= max_files:
                return out
    return out


def toml_get(text, key):
    m = re.search(rf'(?m)^\s*{re.escape(key)}\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else None


def inspect(root):
    files = walk(root)
    lower = {f.lower(): f for f in files}
    top = [f for f in files if os.sep not in f]
    r = {"path": os.path.abspath(root)}

    # ---------- identity ----------
    remote = sh(["git", "remote", "get-url", "origin"], root)
    m = re.search(r"github\.com[:/]([^/]+)/([^/\s]+)", remote)
    r["owner"] = m.group(1) if m else None
    if m:
        r["repo"] = m.group(2).removesuffix(".git")
    else:
        r["repo"] = os.path.basename(os.path.abspath(root))
    origin_head = sh(["git", "rev-parse", "--abbrev-ref", "origin/HEAD"], root)
    if origin_head.startswith("origin/"):
        origin_head = origin_head.removeprefix("origin/")
    # Failed rev-parse still prints origin/HEAD; that is not a branch name.
    if origin_head == "HEAD":
        origin_head = ""
    current_branch = sh(["git", "symbolic-ref", "--short", "HEAD"], root)
    r["default_branch"] = origin_head or current_branch or None
    r["last_commit"] = sh(["git", "log", "-1", "--format=%ci"], root) or None
    r["commit_count"] = sh(["git", "rev-list", "--count", "HEAD"], root) or None
    r["contributors"] = len([l for l in sh(["git", "shortlog", "-sn", "HEAD"], root).splitlines() if l])

    # ---------- manifests ----------
    man = {}
    name = desc = version = None
    ecosystems, install, run_cmds, test_cmds = [], [], [], []

    if "package.json" in lower:
        try:
            pkg = json.loads(read(os.path.join(root, lower["package.json"])))
        except json.JSONDecodeError:
            pkg = None
        if pkg is not None:
            man["package.json"] = {
                k: pkg.get(k) for k in ("name", "version", "description", "license", "bin", "private", "workspaces")
            }
            name = name or pkg.get("name")
            desc = desc or pkg.get("description")
            version = version or pkg.get("version")
            pkg_name = pkg.get("name")
            if not pkg.get("private"):
                ecosystems.append("npm")
                if isinstance(pkg_name, str) and pkg_name:
                    if pkg.get("bin"):
                        install.append(f"npm install -g {pkg_name}")
                    else:
                        install.append(f"npm install {pkg_name}")
            scripts = pkg.get("scripts") or {}
            for k in ("dev", "start", "build"):
                if k in scripts:
                    run_cmds.append(f"npm run {k}")
            for k in ("test", "test:unit"):
                if k in scripts:
                    test_cmds.append(f"npm run {k}")
            r["node_engines"] = (pkg.get("engines") or {}).get("node")

    if "pyproject.toml" in lower:
        t = read(os.path.join(root, lower["pyproject.toml"]))
        man["pyproject.toml"] = {
            "name": toml_get(t, "name"),
            "version": toml_get(t, "version"),
            "description": toml_get(t, "description"),
            "requires-python": toml_get(t, "requires-python"),
        }
        name = name or man["pyproject.toml"]["name"]
        desc = desc or man["pyproject.toml"]["description"]
        version = version or man["pyproject.toml"]["version"]
        ecosystems.append("pypi")
        if man["pyproject.toml"]["name"]:
            install.append(f"pip install {man['pyproject.toml']['name']}")
        if re.search(r"\[project\.scripts\]", t):
            r["console_scripts"] = re.findall(
                r'(?m)^\s*([\w.-]+)\s*=\s*["\']', t.split("[project.scripts]", 1)[1][:500]
            )

    if "cargo.toml" in lower:
        t = read(os.path.join(root, lower["cargo.toml"]))
        name = name or toml_get(t, "name")
        desc = desc or toml_get(t, "description")
        version = version or toml_get(t, "version")
        ecosystems.append("crates.io")
        if name:
            install.append(f"cargo install {name}")
    if "go.mod" in lower:
        t = read(os.path.join(root, lower["go.mod"]))
        mod = re.search(r"(?m)^module\s+(\S+)", t)
        if mod:
            man["go.mod"] = mod.group(1)
            name = name or mod.group(1).split("/")[-1]
            ecosystems.append("go")
            install.append(f"go install {mod.group(1)}@latest")
        gov = re.search(r"(?m)^go\s+([\d.]+)", t)
        r["go_version"] = gov.group(1) if gov else None
    if "gemfile" in lower or any(f.endswith(".gemspec") for f in top):
        ecosystems.append("rubygems")
    if "composer.json" in lower:
        ecosystems.append("packagist")
    if any(f.lower() in ("pom.xml", "build.gradle", "build.gradle.kts") for f in top):
        ecosystems.append("maven/gradle")

    dockerfiles = [f for f in files if os.path.basename(f).lower().startswith("dockerfile")]
    composes = [f for f in files if re.match(r"(docker-)?compose\.ya?ml$", os.path.basename(f).lower())]
    if dockerfiles or composes:
        ecosystems.append("docker")
        if composes:
            run_cmds.append("docker compose up")
    if "makefile" in lower:
        mk = read(os.path.join(root, lower["makefile"]))
        r["make_targets"] = re.findall(r"(?m)^([a-zA-Z][\w-]*):(?!=)", mk)[:15]

    r["manifests"] = man
    r["name"] = name
    r["description_from_manifest"] = desc
    r["version"] = version
    r["ecosystems"] = ecosystems
    r["suggested_install_commands"] = install
    r["suggested_run_commands"] = run_cmds
    r["test_commands"] = test_cmds

    # ---------- language mix ----------
    ext = {}
    for f in files:
        e = os.path.splitext(f)[1].lower()
        if e in (
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".go",
            ".rs",
            ".java",
            ".rb",
            ".php",
            ".c",
            ".cpp",
            ".cs",
            ".swift",
            ".kt",
            ".sh",
            ".lua",
            ".ex",
            ".scala",
        ):
            ext[e] = ext.get(e, 0) + 1
    r["language_mix"] = sorted(ext.items(), key=lambda kv: -kv[1])[:5]
    r["file_count"] = len(files)

    # ---------- health files ----------
    def find(*names):
        for n in names:
            for f in files:
                if os.path.basename(f).lower() == n and f.count(os.sep) <= 1:
                    return f
        return None

    health = {
        "readme": find("readme.md", "readme.rst", "readme.txt", "readme"),
        "license": find("license", "license.md", "license.txt", "licence", "copying"),
        "contributing": find("contributing.md", "contributing.rst"),
        "code_of_conduct": find("code_of_conduct.md"),
        "security": find("security.md"),
        "changelog": find("changelog.md", "changes.md", "history.md"),
        "citation": find("citation.cff"),
        "issue_templates": [f for f in files if "issue_template" in f.lower()][:5],
    }
    r["health_files"] = health
    lic_text = read(os.path.join(root, health["license"]), 4000) if health["license"] else ""
    r["license_guess"] = None
    for pat, nm in (
        (r"MIT License", "MIT"),
        (r"Apache License.*2\.0", "Apache-2.0"),
        (r"GNU AFFERO", "AGPL-3.0"),
        (r"GNU GENERAL PUBLIC LICENSE.*Version 3", "GPL-3.0"),
        (r"GNU LESSER", "LGPL"),
        (r"BSD 3-Clause", "BSD-3-Clause"),
        (r"BSD 2-Clause", "BSD-2-Clause"),
        (r"Mozilla Public License", "MPL-2.0"),
        (r"Business Source License", "BUSL-1.1"),
        (r"The Unlicense", "Unlicense"),
    ):
        if re.search(pat, lic_text, flags=re.IGNORECASE | re.DOTALL):
            r["license_guess"] = nm
            break

    # ---------- CI ----------
    wf = [f for f in files if f.startswith(os.path.join(".github", "workflows"))]
    r["ci_workflows"] = wf[:10]
    r["ci_primary"] = next(
        (os.path.basename(w) for w in wf if re.search(r"ci|test|build|main", os.path.basename(w), re.IGNORECASE)),
        os.path.basename(wf[0]) if wf else None,
    )

    # ---------- docs and assets ----------
    r["docs_dirs"] = sorted(
        {f.split(os.sep)[0] for f in files if f.split(os.sep)[0] in ("docs", "doc", "website", "documentation")}
    )
    r["examples_dirs"] = sorted(
        {f.split(os.sep)[0] for f in files if f.split(os.sep)[0] in ("examples", "example", "samples", "demo")}
    )
    r["images"] = [
        f
        for f in files
        if os.path.splitext(f)[1].lower() in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
        and not f.startswith("node_modules")
    ][:20]
    r["has_demo_media"] = [f for f in r["images"] if f.lower().endswith((".gif", ".webp"))] + [
        f for f in files if f.lower().endswith((".mp4", ".webm", ".cast"))
    ]

    # ---------- existing README ----------
    rd = read(os.path.join(root, health["readme"])) if health["readme"] else ""
    r["readme"] = {
        "exists": bool(rd),
        "bytes": len(rd),
        "lines": rd.count("\n") + 1 if rd else 0,
        "h1_count": len(re.findall(r"(?m)^# ", rd)),
        "headings": re.findall(r"(?m)^#{2,3}\s+(.+)$", rd)[:40],
        "badges": len(re.findall(r"img\.shields\.io|badge\.svg", rd)),
        "code_blocks": rd.count("```") // 2,
        "images": len(re.findall(r"!\[[^\]]*\]\(|<img ", rd)),
        "links_docs_site": bool(re.search(r"https?://(docs?|www)\.", rd)),
    }

    # ---------- community links found anywhere ----------
    blob = rd + read(os.path.join(root, "package.json"), 20000)
    r["community_links"] = sorted(
        set(
            re.findall(
                r'https?://(?:discord\.(?:gg|com)|join\.slack\.com|matrix\.to|t\.me|[\w.-]*reddit\.com)[^\s)\'"]*', blob
            )
        )
    )[:5]
    r["docs_links"] = sorted(set(re.findall(r'https?://(?:docs?|www)\.[^\s)\'"]+', blob)))[:5]

    # ---------- gaps ----------
    gaps = []
    if not health["readme"]:
        gaps.append("No README at all.")
    if not health["license"]:
        gaps.append("No LICENSE file: add one before claiming a license in the README.")
    if not health["contributing"]:
        gaps.append("No CONTRIBUTING.md: either create it or do not link it.")
    if not r["images"]:
        gaps.append("No images in repo: a demo GIF or screenshot must be created or the visual section cut.")
    if not wf:
        gaps.append("No CI workflows: do not add a CI badge.")
    if not ecosystems:
        gaps.append("No package manifest found: install instructions must be clone-and-run.")
    if not r["docs_dirs"] and not r["docs_links"]:
        gaps.append("No docs site or docs/ dir: Documentation section should link in-repo files or be cut.")
    r["gaps"] = gaps
    return r


def human(r):
    L = []
    a = L.append
    a(
        f"REPO        {r['owner'] or '?'}/{r['repo']}   branch={r['default_branch']}  commits={r['commit_count']}  contributors={r['contributors']}"
    )
    a(f"NAME        {r['name']}")
    a(f"DESCRIPTION {r['description_from_manifest']}")
    a(f"VERSION     {r['version']}    ECOSYSTEMS: {', '.join(r['ecosystems']) or 'none'}")
    a(f"LANGUAGES   {r['language_mix']}   files={r['file_count']}")
    a(f"LICENSE     file={r['health_files']['license']}  detected={r['license_guess']}")
    a(f"CI          {r['ci_primary']}  ({len(r['ci_workflows'])} workflows)")
    a(f"DOCS        dirs={r['docs_dirs']}  links={r['docs_links']}")
    a(f"EXAMPLES    {r['examples_dirs']}")
    a(f"MEDIA       demo={r['has_demo_media'][:3]}  images={len(r['images'])}")
    a(f"COMMUNITY   {r['community_links']}")
    a(
        "HEALTH      "
        + ", ".join(f"{k}={'Y' if v else 'N'}" for k, v in r["health_files"].items() if k != "issue_templates")
    )
    a(f"INSTALL?    {r['suggested_install_commands']}")
    a(f"RUN?        {r['suggested_run_commands']}   TEST? {r['test_commands']}")
    if r["readme"]["exists"]:
        rd = r["readme"]
        a(
            f"README      {rd['lines']} lines, {rd['badges']} badges, {rd['code_blocks']} code blocks, {rd['images']} images, h1={rd['h1_count']}"
        )
        a(f"  sections: {rd['headings']}")
    else:
        a("README      none")
    if r["gaps"]:
        a("GAPS (resolve before writing; ask the user rather than inventing):")
        for g in r["gaps"]:
            a(f"  - {g}")
    return "\n".join(L)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    root = args[0] if args else "."
    res = inspect(root)
    if "--json" in sys.argv:
        print(json.dumps(res, indent=2))
    else:
        print(human(res))
