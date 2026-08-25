set shell := ["bash", "-uc"]

# Recipes take no extra arguments. For a pytest subset: uv run pytest <paths>

default:
    @just --list

# Validate every rule, skill, hook, agent, and loadout definition in this repo
lint:
    uv run loadout lint

format:
    uv run ruff check --fix
    uv run ruff format

# Full pytest suite (no path arguments)
test:
    uv run pytest

# Static type check with pyrefly
typecheck:
    uv run pyrefly check

# Push the current release/vX.Y.Z branch and open a PR. CI tags on merge. usage: just release 1.5.0
release version:
    #!/usr/bin/env bash
    set -euo pipefail

    version="{{version}}"
    expected_branch="release/v${version}"
    current_branch="$(git branch --show-current)"
    if [[ "${current_branch}" != "${expected_branch}" ]]; then
      echo "error: must be on ${expected_branch} (currently on ${current_branch:-detached HEAD})" >&2
      exit 1
    fi

    grep -q "## ${version}" CHANGELOG.md || { echo "no CHANGELOG entry for ${version}"; exit 1; }

    py_version="$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n1)"
    init_version="$(sed -n 's/^__version__ = "\([^"]*\)"/\1/p' src/loadout/__init__.py | head -n1)"
    if [[ "${py_version}" != "${version}" ]]; then
      echo "error: pyproject.toml version is ${py_version}, expected ${version}" >&2
      exit 1
    fi
    if [[ "${init_version}" != "${version}" ]]; then
      echo "error: __version__ is ${init_version}, expected ${version}" >&2
      exit 1
    fi

    if git show-ref --verify --quiet refs/remotes/origin/main; then
      base_branch="main"
    elif git show-ref --verify --quiet refs/remotes/origin/master; then
      base_branch="master"
    else
      echo "error: neither origin/main nor origin/master found" >&2
      exit 1
    fi

    just lint && just typecheck && just test
    git push -u origin HEAD

    if pr_url="$(gh pr view --json url -q .url 2>/dev/null)"; then
      echo "PR already exists: ${pr_url}"
    else
      body="$(printf '%s\n' \
        "## Summary" \
        "- Prepare release **v${version}** on \`${expected_branch}\`." \
        "" \
        "## Test plan" \
        "- [ ] CI green on this PR" \
        "- [ ] After merge, confirm annotated tag \`v${version}\` exists on the merge commit")"
      gh pr create --base "${base_branch}" --head "${expected_branch}" \
        --title "release: v${version}" \
        --body "${body}"
    fi

    echo "Next: merge the PR; CI will create annotated tag v${version} on the merge commit."

try project:
    LOADOUT_PATH="$(pwd)" just -f "{{project}}/justfile" loadout-sync

# Import a third-party skill into skills/ for use in loadouts using similar syntax to common `npx -y skills add ...` CLI commands.
# Example usage: just add_skill mattpocock/skills --skill grill-me
# If Just swallows flags: just add_skill mattpocock/skills -- --skill grill-me
[positional-arguments]
add_skill *args:
    #!/usr/bin/env bash
    set -euo pipefail

    if [[ $# -lt 1 ]]; then
      echo "usage: just add_skill <package> [--skill <name>] ..." >&2
      exit 1
    fi

    filtered=()
    skip_next=0
    has_yes=0
    for arg in "$@"; do
      if [[ $skip_next -eq 1 ]]; then
        skip_next=0
        continue
      fi
      case "$arg" in
        -g|--global)
          echo "error: --global is not supported; skills must land in this repo's skills/" >&2
          exit 1
          ;;
        -a|--agent)
          skip_next=1
          continue
          ;;
        --agent=*)
          continue
          ;;
        --copy)
          continue
          ;;
        -y|--yes)
          has_yes=1
          filtered+=("$arg")
          ;;
        *)
          filtered+=("$arg")
          ;;
      esac
    done

    extra=(-a claude-code --copy)
    if [[ $has_yes -eq 0 ]]; then
      extra+=(-y)
    fi

    # skills CLI may stage under .claude/skills and/or .agents/skills
    stage_dirs=(".claude/skills" ".agents/skills")
    for staging in "${stage_dirs[@]}"; do
      mkdir -p "$staging"
    done

    before_file="$(mktemp)"
    after_file="$(mktemp)"
    trap 'rm -f "$before_file" "$after_file"' EXIT

    {
      for staging in "${stage_dirs[@]}"; do
        ls -1 "$staging" 2>/dev/null || true
      done
    } | sort -u >"$before_file"

    npx -y skills add "${filtered[@]}" "${extra[@]}"

    {
      for staging in "${stage_dirs[@]}"; do
        ls -1 "$staging" 2>/dev/null || true
      done
    } | sort -u >"$after_file"
    new_skills="$(comm -13 "$before_file" "$after_file")"

    if [[ -z "$new_skills" ]]; then
      echo "error: no new skills appeared under .claude/skills/ or .agents/skills/" >&2
      exit 1
    fi

    mkdir -p skills
    moved=()
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      if [[ -e "skills/${name}" ]]; then
        echo "error: skills/${name} already exists; remove it first" >&2
        exit 1
      fi

      source_path=""
      for staging in "${stage_dirs[@]}"; do
        if [[ -d "${staging}/${name}" ]]; then
          source_path="${staging}/${name}"
          break
        fi
      done
      if [[ -z "$source_path" ]]; then
        echo "error: staged skill ${name} not found in staging dirs" >&2
        exit 1
      fi

      mv "$source_path" "skills/${name}"
      # Drop duplicate staging copies of the same skill
      for staging in "${stage_dirs[@]}"; do
        rm -rf "${staging}/${name}"
      done
      moved+=("$name")
    done <<<"$new_skills"

    for staging in "${stage_dirs[@]}"; do
      rmdir "$staging" 2>/dev/null || true
    done
    rmdir .claude 2>/dev/null || true
    rmdir .agents 2>/dev/null || true
    rm -f skills-lock.json .skills.json

    echo "Imported into skills/:"
    for name in "${moved[@]}"; do
      echo "  skills/${name}"
    done
    echo "Add each to a loadout YAML (or project include), then run: just lint"
