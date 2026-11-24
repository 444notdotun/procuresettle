#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

if cargo fmt --all -- --check; then
    echo "Formatting check passed: all Rust files are formatted."
    exit 0
fi

status=$?
echo "Formatting check failed: one or more Rust files need formatting." >&2
echo "Remediation: run 'cargo fmt --all' from $ROOT_DIR, review the changes, and re-run 'scripts/check-fmt.sh'." >&2
exit "$status"
