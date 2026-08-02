# Consumer contract

This document describes what generated projects and the cookiecutter template must implement. The loadout repo owns the CLI and content; consumers own wiring it into project scaffolding.

## Project `justfile`

Generated projects include these recipes (spec §7.2):

```just
source_ref := `grep '^ref:' .loadout.yaml | awk '{print $2}'`
source_url := `grep '^source:' .loadout.yaml | awk '{print $2}'`
loadout := "uvx --from git+" + source_url + "@" + source_ref + " loadout"

# Apply the pinned rules and skills to this repo
loadout-sync:
    {{loadout}} sync

# Fail if .cursor/ does not match the lockfile
loadout-check:
    {{loadout}} sync --check

# Bump to the latest release and re-sync
loadout-update:
    {{loadout}} update

# List what the current manifest resolves to
loadout-list:
    {{loadout}} resolve --list
```

## Cookiecutter post-generation hook

The hook is a **thin caller**. It must not duplicate copy logic — day-0 generation and day-100 updates run the same `loadout sync` path.

Responsibilities (spec §8.1):

1. Map cookiecutter answers to loadout names (never file lists).
2. Write `.loadout.yaml`.
3. Run `just loadout-sync`.
4. On success, `git add` the generated `.cursor/` output for the initial commit.

Example mapping:

```python
LOADOUTS = ["base", "python-monorepo"]

if ctx["use_terraform"] == "yes":
    LOADOUTS.append("aws-terraform")
if ctx["use_playwright"] == "yes":
    LOADOUTS.append("playwright-e2e")
```

### Hook must never hard-fail

Cookiecutter deletes the entire output directory if a post-gen hook exits nonzero. Network errors, expired tokens, or proxy issues must not destroy a freshly generated project.

Required behavior: catch every exception from the sync step, print a clear warning naming `just loadout-sync` as the fix, leave `.loadout.yaml` in place, and exit 0.

```python
try:
    subprocess.run(["just", "loadout-sync"], check=True)
except Exception as exc:
    print(f"WARNING: could not sync rules and skills: {exc}")
    print("Project generated successfully. Run `just loadout-sync` when you have network access.")
```

## Hermetic template tests

Template tests set `LOADOUT_PATH` to a checked-out loadout repo fixture so generation is offline and hermetic — no network, no git clone. The lockfile records `"resolved_sha": "local"` and `sync --check` warns rather than failing on SHA mismatch.

```bash
LOADOUT_PATH=/path/to/loadout-fixture just loadout-sync
```

## Project CI

Generated projects should run drift checks on every PR:

```yaml
- name: Verify agent rules and skills
  run: just loadout-check
```
