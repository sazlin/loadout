set shell := ["bash", "-uc"]

default:
    @just --list

lint:
    uv run loadout lint

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
