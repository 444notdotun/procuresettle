#!/usr/bin/env bash

# Demonstrate the complete ProcureSettle lifecycle against a local Stellar
# standalone container using the Stellar CLI.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/demo-flow.sh [options]

Run the complete ProcureSettle flagship flow against a local Stellar network.

Prerequisites:
  - Docker with the Docker daemon running
  - Stellar CLI 28.1.0
  - Rust 1.95.0 and the wasm32v1-none Rust target
  - The local Stellar container must be running

Options:
  --network <name>       Stellar network name (default: local)
  --config-dir <path>    Stellar CLI config directory
                         (default: .stellar-demo)
  --po-id <id>           Purchase order ID (default: 125)
  -h, --help             Show this help
EOF
}

die() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

step() {
  printf '\n==> %s\n' "$1"
}

network="${NETWORK:-local}"
config_dir="${STELLAR_CONFIG_DIR:-$PWD/.stellar-demo}"
po_id="${PO_ID:-125}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --network)
      [[ $# -ge 2 ]] || die "--network requires a value"
      network="$2"
      shift 2
      ;;
    --config-dir)
      [[ $# -ge 2 ]] || die "--config-dir requires a value"
      config_dir="$2"
      shift 2
      ;;
    --po-id)
      [[ $# -ge 2 ]] || die "--po-id requires a positive integer"
      po_id="$2"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[[ "$po_id" =~ ^[1-9][0-9]*$ ]] || die "--po-id must be a positive integer"

command -v stellar >/dev/null 2>&1 || die "stellar CLI is not installed"
command -v docker >/dev/null 2>&1 || die "Docker is not installed"
mkdir -p "$config_dir"

stellar_cli=(stellar --config-dir "$config_dir")

step "Checking local Stellar network"
"${stellar_cli[@]}" network info >/dev/null 2>&1 ||
  die "network '$network' is unavailable; start it with 'stellar container start $network'"

step "1/6 Creating mock identities"
for identity in issuer buyer supplier; do
  if ! "${stellar_cli[@]}" keys public-key "$identity" >/dev/null 2>&1; then
    "${stellar_cli[@]}" keys generate "$identity" --network "$network" --fund >/dev/null
  fi
done
issuer=$("${stellar_cli[@]}" keys public-key issuer)
buyer=$("${stellar_cli[@]}" keys public-key buyer)
supplier=$("${stellar_cli[@]}" keys public-key supplier)
printf '  issuer:   %s\n  buyer:    %s\n  supplier: %s\n' "$issuer" "$buyer" "$supplier"

step "2/6 Building and deploying contracts"
stellar contract build --locked --package procuresettle >/dev/null
wasm="$PWD/target/wasm32v1-none/release/procuresettle.wasm"
[[ -f "$wasm" ]] || die "built WASM was not found at $wasm"

asset="PSET:$issuer"
"${stellar_cli[@]}" tx new change-trust \
  --source-account buyer --line "$asset" --network "$network" >/dev/null
"${stellar_cli[@]}" tx new change-trust \
  --source-account supplier --line "$asset" --network "$network" >/dev/null
"${stellar_cli[@]}" tx new payment \
  --source-account issuer --destination "$buyer" \
  --asset "$asset" --amount 1000000000 --network "$network" >/dev/null

sac_id=$(
  "${stellar_cli[@]}" contract asset deploy \
    --asset "$asset" --source-account issuer --network "$network"
)
contract_id=$(
  "${stellar_cli[@]}" contract deploy \
    --wasm "$wasm" --source-account issuer --network "$network"
)
printf '  SAC:      %s\n  contract: %s\n' "$sac_id" "$contract_id"

step "3/6 Creating PO with 2 lines"
lines='[{"line_id":1,"ordered_quantity":10,"unit_price":"6"},{"line_id":2,"ordered_quantity":8,"unit_price":"5"}]'
"${stellar_cli[@]}" contract invoke \
  --contract-id "$contract_id" --source-account buyer --network "$network" \
  -- create_po --po_id "$po_id" --buyer "$buyer" --supplier "$supplier" \
  --token "$sac_id" --lines "$lines" >/dev/null
printf '  PO %s: 2 lines, total 100 base units\n' "$po_id"

step "4/6 Accepting and funding PO"
"${stellar_cli[@]}" contract invoke \
  --contract-id "$contract_id" --source-account supplier --network "$network" \
  -- accept_po --po_id "$po_id" >/dev/null
"${stellar_cli[@]}" contract invoke \
  --contract-id "$contract_id" --source-account buyer --network "$network" \
  -- fund_po --po_id "$po_id" >/dev/null
printf '  PO %s: Accepted then Funded\n' "$po_id"

step "5/6 Submitting and settling receipt"
receipt='[{"line_id":1,"quantity_delta":10},{"line_id":2,"quantity_delta":8}]'
"${stellar_cli[@]}" contract invoke \
  --contract-id "$contract_id" --source-account supplier --network "$network" \
  -- submit_receipt --po_id "$po_id" --receipt_id 1 --quantities "$receipt" >/dev/null
settlement=$(
  "${stellar_cli[@]}" contract invoke \
    --contract-id "$contract_id" --source-account buyer --network "$network" \
    -- accept_receipt_and_settle --po_id "$po_id" --receipt_id 1
)
printf '  Receipt 1 settled for %s base units\n' "$settlement"

step "6/6 Inspecting final PO status"
po_json=$(
  "${stellar_cli[@]}" contract invoke \
    --contract-id "$contract_id" --source-account buyer --network "$network" \
    -- get_po --po_id "$po_id"
)
printf '%s\n' "$po_json"

if grep -q '"status":"Closed"' <<<"$po_json" || grep -q '"status": "Closed"' <<<"$po_json"; then
  printf '\nSuccess: PO %s is Closed.\n' "$po_id"
else
  printf '\nWarning: PO %s did not report status Closed.\n' "$po_id" >&2
  exit 1
fi
