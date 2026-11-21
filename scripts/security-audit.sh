#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -f Cargo.lock ]]; then
  echo "Cargo.lock is required; run this audit from a Rust workspace with a committed lockfile." >&2
  exit 1
fi

if ! cargo audit --version >/dev/null 2>&1; then
  echo "cargo-audit is not installed." >&2
  echo "Install it with: cargo install cargo-audit --locked --version 0.23.0" >&2
  exit 127
fi

cargo audit --deny warnings "$@"
