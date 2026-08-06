set shell := ["bash", "-uc"]

default:
    @just --list

# Validate every rule, skill, hook, agent, and loadout definition in this repo
lint:
    uv run loadout lint

format:
    uv run ruff check --fix
    uv run ruff format

test:
    uv run pytest

release version:
    #!/usr/bin/env bash
    set -euo pipefail
    grep -q "## {{version}}" CHANGELOG.md || { echo "no CHANGELOG entry for {{version}}"; exit 1; }
    just lint && just test
    git tag -a "v{{version}}" -m "v{{version}}"
    git push origin "v{{version}}"

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
