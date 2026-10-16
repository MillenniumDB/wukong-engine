#!/usr/bin/env bash
# PostToolUse hook: auto-fix and format an edited Python file with the locked Ruff,
# then hand whatever Ruff couldn't fix back to Claude (exit 2 feeds stderr to it).
set -uo pipefail

file=$(jq -r '.tool_input.file_path // empty')
# Files outside the repo (scratchpad, other projects) aren't governed by this config.
[[ "$file" == *.py && "$file" == "$CLAUDE_PROJECT_DIR"/* ]] || exit 0
cd "$CLAUDE_PROJECT_DIR" || exit 0

poetry run ruff check --fix --force-exclude --quiet "$file" >/dev/null 2>&1
poetry run ruff format --force-exclude --quiet "$file" >/dev/null 2>&1

if ! output=$(poetry run ruff check --force-exclude --output-format concise "$file" 2>&1); then
    printf 'Ruff found issues it could not fix in %s:\n%s\n' "$file" "$output" >&2
    exit 2
fi
