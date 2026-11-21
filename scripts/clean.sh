#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/clean.sh [OPTIONS]

Safely remove build targets, stray WASM outputs, Python cache files, and
temporary test configs from the ProcureSettle repository.

Targets removed:
  - target/
  - *.wasm (untracked build outputs)
  - __pycache__/ directories and *.pyc files
  - .tmp* temporary test files/directories

Options:
  -n, --dry-run      List paths that would be removed without deleting them
  -i, --interactive  Prompt for confirmation before removing paths
  -y, --yes          Remove matching paths without prompting (default)
  -h, --help         Show this help message and exit
EOF
}

dry_run=false
interactive=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--dry-run)
      dry_run=true
      shift
      ;;
    -i|--interactive)
      interactive=true
      shift
      ;;
    -y|--yes)
      interactive=false
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "$repo_root" || "$repo_root" == "/" ]]; then
  echo "Error: refusing to clean unsafe repository root: '${repo_root}'" >&2
  exit 1
fi

if [[ ! -f "$repo_root/Cargo.toml" || ! -f "$repo_root/contracts/po-settlement/Cargo.toml" ]]; then
  echo "Error: expected ProcureSettle repository root at '$repo_root' (Cargo.toml not found)." >&2
  exit 1
fi

declare -a targets=()

if [[ -d "$repo_root/target" ]]; then
  targets+=("$repo_root/target")
fi

# Collect __pycache__ directories, *.pyc files, *.wasm outputs, and .tmp* entries
# outside .git and target/ (target/ is handled as a single entry above).
while IFS= read -r -d '' entry; do
  targets+=("$entry")
done < <(
  find "$repo_root" \
    \( -path "$repo_root/.git" -o -path "$repo_root/target" \) -prune -o \
    \( -type d -name '__pycache__' -print0 -prune \) -o \
    \( -name '.tmp*' -print0 -prune \) -o \
    \( -type f \( -name '*.pyc' -o -name '*.wasm' \) -print0 \)
)

if [[ ${#targets[@]} -eq 0 ]]; then
  echo "Workspace is already clean; no build artifacts or cache files found."
  exit 0
fi

# Sort targets for deterministic output.
declare -a sorted_targets=()
while IFS= read -r entry; do
  sorted_targets+=("$entry")
done < <(printf '%s\n' "${targets[@]}" | sort -u)

echo "Clean targets in ${repo_root}:"
for path in "${sorted_targets[@]}"; do
  rel="${path#"$repo_root"/}"
  echo "  - ${rel}"
done

if [[ "$dry_run" == true ]]; then
  echo "Dry run complete: ${#sorted_targets[@]} item(s) would be removed."
  exit 0
fi

if [[ "$interactive" == true ]]; then
  read -r -p "Remove ${#sorted_targets[@]} item(s)? [y/N] " reply
  case "$reply" in
    y|Y|yes|YES)
      ;;
    *)
      echo "Cleanup aborted; no files were removed."
      exit 0
      ;;
  esac
fi

removed=0
for path in "${sorted_targets[@]}"; do
  # Explicit safety checks before every removal.
  if [[ "$path" != "$repo_root/"* || "$path" == "$repo_root" || "$path" == "$repo_root/.git" || "$path" == "$repo_root/.git/"* ]]; then
    echo "Error: refusing to remove unsafe path: '$path'" >&2
    exit 1
  fi
  if [[ -e "$path" || -L "$path" ]]; then
    rm -rf -- "$path"
    removed=$((removed + 1))
  fi
done

echo "Clean complete: removed ${removed} item(s)."
