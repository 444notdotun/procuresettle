#!/usr/bin/env bash

set -euo pipefail

FRIENDBOT_URL="${FRIENDBOT_URL:-https://friendbot.stellar.org}"
HORIZON_URL="${HORIZON_URL:-https://horizon-testnet.stellar.org}"

timeout_seconds=60
poll_interval=2
curl_timeout=15

usage() {
  cat <<'EOF'
Usage: ./scripts/fund-testnet-account.sh [OPTIONS] <G...PUBLIC_KEY>

Request Stellar Testnet funding for a public key via Friendbot and poll
Horizon until the account is active on the ledger.

Arguments:
  <G...PUBLIC_KEY>        Stellar Ed25519 public key (56 chars starting with G)

Options:
  --timeout SECONDS       Overall Horizon polling timeout in seconds (default: 60)
  --interval SECONDS      Seconds between Horizon poll attempts (default: 2)
  --curl-timeout SECONDS  Per-request curl timeout in seconds (default: 15)
  -h, --help              Show this help message and exit

Environment variables:
  FRIENDBOT_URL           Override Friendbot base URL (default: https://friendbot.stellar.org)
  HORIZON_URL             Override Horizon base URL (default: https://horizon-testnet.stellar.org)
EOF
}

is_positive_int() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

public_key=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout)
      if [[ $# -lt 2 ]] || ! is_positive_int "$2"; then
        echo "Error: --timeout requires a positive integer." >&2
        exit 2
      fi
      timeout_seconds="$2"
      shift 2
      ;;
    --interval)
      if [[ $# -lt 2 ]] || ! is_positive_int "$2"; then
        echo "Error: --interval requires a positive integer." >&2
        exit 2
      fi
      poll_interval="$2"
      shift 2
      ;;
    --curl-timeout)
      if [[ $# -lt 2 ]] || ! is_positive_int "$2"; then
        echo "Error: --curl-timeout requires a positive integer." >&2
        exit 2
      fi
      curl_timeout="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -n "$public_key" ]]; then
        echo "Error: unexpected extra argument: $1" >&2
        usage >&2
        exit 2
      fi
      public_key="$1"
      shift
      ;;
  esac
done

if [[ -z "$public_key" ]]; then
  echo "Error: missing required <G...PUBLIC_KEY> argument." >&2
  usage >&2
  exit 2
fi

if [[ ! "$public_key" =~ ^G[A-Z2-7]{55}$ ]]; then
  echo "Error: invalid Stellar public key: '$public_key' (expected 56-character G... StrKey)." >&2
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "Error: curl is required but was not found in PATH." >&2
  exit 127
fi

has_jq=false
if command -v jq >/dev/null 2>&1; then
  has_jq=true
fi

friendbot_endpoint="${FRIENDBOT_URL%/}?addr=${public_key}"
horizon_endpoint="${HORIZON_URL%/}/accounts/${public_key}"

echo "Requesting Testnet funding from Friendbot for ${public_key}..."

friendbot_raw=""
friendbot_curl_rc=0
friendbot_raw="$(
  curl --silent --show-error \
    --connect-timeout "$curl_timeout" \
    --max-time "$curl_timeout" \
    --write-out $'\n%{http_code}' \
    "$friendbot_endpoint"
)" || friendbot_curl_rc=$?

if [[ "$friendbot_curl_rc" -ne 0 ]]; then
  echo "Error: Friendbot request failed (curl exit code ${friendbot_curl_rc})." >&2
  exit 1
fi

friendbot_status="${friendbot_raw##*$'\n'}"
friendbot_body="${friendbot_raw%$'\n'*}"

if [[ "$friendbot_status" -ge 200 && "$friendbot_status" -lt 300 ]]; then
  echo "Friendbot accepted funding request (HTTP ${friendbot_status})."
elif [[ "$friendbot_status" -eq 400 && "$friendbot_body" == *"createAccountAlreadyExist"* ]]; then
  echo "Account is already funded on Testnet (HTTP 400: createAccountAlreadyExist); verifying on Horizon..."
else
  echo "Error: Friendbot returned HTTP ${friendbot_status}." >&2
  if [[ -n "$friendbot_body" ]]; then
    echo "$friendbot_body" >&2
  fi
  exit 1
fi

echo "Polling Horizon (${horizon_endpoint}) for account confirmation (timeout: ${timeout_seconds}s)..."

deadline=$((SECONDS + timeout_seconds))
attempt=0
last_status=""
last_error=""

while true; do
  attempt=$((attempt + 1))
  remaining=$((deadline - SECONDS))
  if [[ "$remaining" -le 0 ]]; then
    break
  fi

  req_timeout="$curl_timeout"
  if [[ "$remaining" -lt "$req_timeout" ]]; then
    req_timeout="$remaining"
  fi

  horizon_raw=""
  horizon_curl_rc=0
  horizon_raw="$(
    curl --silent --show-error \
      --connect-timeout "$req_timeout" \
      --max-time "$req_timeout" \
      --write-out $'\n%{http_code}' \
      "$horizon_endpoint" 2>&1
  )" || horizon_curl_rc=$?

  if [[ "$horizon_curl_rc" -ne 0 ]]; then
    last_error="curl exit ${horizon_curl_rc}: ${horizon_raw}"
    echo "Attempt ${attempt}: Horizon request error (curl exit ${horizon_curl_rc}); retrying..." >&2
  else
    horizon_status="${horizon_raw##*$'\n'}"
    horizon_body="${horizon_raw%$'\n'*}"
    last_status="$horizon_status"

    if [[ "$horizon_status" -eq 200 ]]; then
      account_matches=false
      if [[ "$has_jq" == true ]]; then
        if printf '%s' "$horizon_body" | jq -e --arg addr "$public_key" '.account_id == $addr' >/dev/null 2>&1; then
          account_matches=true
        fi
      elif [[ "$horizon_body" == *"\"account_id\""* && "$horizon_body" == *"\"${public_key}\""* ]]; then
        account_matches=true
      fi

      if [[ "$account_matches" == true ]]; then
        if [[ "$has_jq" == true ]]; then
          xlm_balance="$(
            printf '%s' "$horizon_body" | jq -r '.balances[]? | select(.asset_type == "native") | .balance' 2>/dev/null | head -n 1 || true
          )"
          if [[ -n "$xlm_balance" ]]; then
            echo "Account ${public_key} is active on Testnet (native XLM balance: ${xlm_balance})."
          else
            echo "Account ${public_key} is active on Testnet."
          fi
        else
          echo "Account ${public_key} is active on Testnet."
        fi
        exit 0
      fi
      last_error="HTTP 200 received but response did not confirm account_id ${public_key}"
    elif [[ "$horizon_status" -eq 404 ]]; then
      last_error="HTTP 404 (account not yet indexed)"
    else
      last_error="HTTP ${horizon_status}"
      echo "Attempt ${attempt}: Horizon returned HTTP ${horizon_status}; retrying..." >&2
    fi
  fi

  remaining=$((deadline - SECONDS))
  if [[ "$remaining" -le 0 ]]; then
    break
  fi
  sleep_for="$poll_interval"
  if [[ "$remaining" -lt "$sleep_for" ]]; then
    sleep_for="$remaining"
  fi
  sleep "$sleep_for"
done

echo "Error: timed out after ${timeout_seconds}s waiting for account ${public_key} on Horizon (attempts: ${attempt}, last status: ${last_status:-none}, detail: ${last_error:-unknown})." >&2
exit 1
