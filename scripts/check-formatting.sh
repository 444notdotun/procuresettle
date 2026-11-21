#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

ERRORS=0

# Check tracked text files matching .rs, .md, .toml, .py, .yml, .yaml
while IFS= read -r file; do
    [ -f "$file" ] || continue

    # Check for trailing whitespace
    while IFS=: read -r line_num rest; do
        if [ -n "$line_num" ]; then
            echo "$file:$line_num: trailing whitespace found"
            ERRORS=$((ERRORS + 1))
        fi
    done < <(grep -n -E '[[:blank:]]+$' "$file" 2>/dev/null || true)

    # Check for missing newline at end of file (non-empty files)
    if [ -s "$file" ]; then
        if [ "$(tail -c 1 "$file")" != "$(printf '\n')" ]; then
            line_count=$(wc -l < "$file" || echo 1)
            echo "$file:$((line_count + 1)): missing final newline at end of file"
            ERRORS=$((ERRORS + 1))
        fi
    fi
done < <(git ls-files '*.rs' '*.md' '*.toml' '*.py' '*.yml' '*.yaml')

if [ "$ERRORS" -gt 0 ]; then
    echo "Formatting check failed: $ERRORS violation(s) found." >&2
    exit 1
fi

echo "Formatting check passed: all tracked text files are cleanly formatted."
exit 0
