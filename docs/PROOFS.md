# Reproduce the protocol-28 local proofs

Run the blocks in order from the repository root in one Bash session on Linux.
Use Docker with a running daemon, a free port 8000, Stellar CLI 28.1.0,
Rust 1.95.0 with the wasm32v1-none target, Python 3.12+ with venv and pip,
curl, jq and GNU coreutils. The [flagship CI job](../.github/workflows/ci.yml)
pins the Quickstart image and runs both harnesses against a fresh ledger.

## Build the contract

```bash
set -euo pipefail
test "$(stellar --version | awk 'NR == 1 {print $2}')" = 28.1.0
work=$(mktemp -d)
config="$work/config"
reports="$work/reports"
mkdir -p "$config" "$reports"
python3 -m venv "$work/venv"
source "$work/venv/bin/activate"
python -m pip install -r requirements-proof.txt
rustup target add --toolchain 1.95.0 wasm32v1-none
stellar contract build --locked --package procuresettle
wasm=target/wasm32v1-none/release/procuresettle.wasm
size=$(stat -c %s "$wasm")
digest=$(sha256sum "$wasm" | cut -d ' ' -f1)
```

## Start the standalone ledger

The CLI accepts a tag override. Tag the image pulled by digest, then check the
running container uses those bytes. Wait for Core to sync and verify the network
passphrase and protocol before creating accounts.

```bash
image=stellar/quickstart@sha256:4f8dfd693deba57fddef7f0bc722e4782c2e606c8675e3adc5438cebae249295
tag=procuresettle-proof-4f8dfd693deb
docker pull "$image"
docker tag "$image" "stellar/quickstart:$tag"
cli=(stellar --config-dir "$config")
name="procuresettle-proof-$$"
"${cli[@]}" container start local --name "$name" --cpus 2 --memory 4g \
  --protocol-version 28 --image-tag-override "$tag"
test "$(docker inspect "stellar-$name" --format '{{.Image}}')" = "$(docker image inspect "$image" --format '{{.Id}}')"
"${cli[@]}" network use local
url=http://localhost:8000
for attempt in {1..60}; do
  if curl -fsS "$url/health" | jq -e '.database_connected and .core_up and .core_synced' >/dev/null &&
     "${cli[@]}" network info --network local >"$reports/network.txt" 2>&1 &&
     grep -Fq 'Protocol Version: 28' "$reports/network.txt"; then break; fi
  sleep 5
done
grep -F 'Protocol Version: 28' "$reports/network.txt"
grep -F 'Standalone Network ; February 2017' "$reports/network.txt"
```

## Fund the actors and deploy the settlement asset

Generate three disposable local keys. Friendbot funds their XLM accounts.
The buyer and supplier open LSP trustlines, then the issuer pays the buyer
1,000 LSP and deploys its Stellar Asset Contract (SAC).

```bash
for actor in issuer buyer supplier; do
  "${cli[@]}" keys generate "$actor"
  address=$("${cli[@]}" keys public-key "$actor")
  for attempt in {1..30}; do
    curl -sS "$url/friendbot?addr=$address" -o /dev/null
    if curl -fsS "$url/accounts/$address" | jq -e --arg a "$address" '.account_id == $a' >/dev/null; then break; fi
    sleep 2
  done
  curl -fsS "$url/accounts/$address" | jq -e --arg a "$address" '.account_id == $a' >/dev/null
done
asset="LSP:$("${cli[@]}" keys public-key issuer)"
buyer=$("${cli[@]}" keys public-key buyer)
supplier=$("${cli[@]}" keys public-key supplier)
for actor in buyer supplier; do
  "${cli[@]}" tx new change-trust --source-account "$actor" --line "$asset" --network local
done
"${cli[@]}" tx new payment --source-account issuer --destination "$buyer" --asset "$asset" --amount 1000 --network local
sac=$("${cli[@]}" contract asset deploy --asset "$asset" --source-account issuer --network local)
```

## Run the proofs and read the reports

```bash
args=(--config-dir "$config" --wasm "$wasm" --expected-wasm-size "$size"
      --expected-wasm-sha256 "$digest" --report-dir "$reports" --sac-id "$sac"
      --issuer-identity issuer --buyer-identity buyer --buyer-address "$buyer"
      --supplier-identity supplier --supplier-address "$supplier")
for proof in flagship cancellation; do
  python "scripts/local-$proof-proof.py" "${args[@]}" | tee "$reports/$proof.stdout"
  sed '1d' "$reports/$proof.stdout" >"$reports/$proof.json"
  jq -e --arg hash "$digest" '.verdict == "PASS" and .wasm_sha256 == $hash' "$reports/$proof.json"
done
python scripts/verify-evidence-checksums.py
printf 'Reports: %s\n' "$reports"
"${cli[@]}" container stop "$name"
```

Each harness prints a heading followed by JSON on success. The loop saves that
JSON separately and preserves the original output. The `report` field names the
detailed CLI transcript. If a command fails, inspect the transcript and use
the final container-stop command to shut down your ledger. Keep the config
directory private because it contains the local signing keys.

- **Flagship.** In `control`, the first and final payouts are 56 and 44 base
  units. The PO closes with 100 paid and zero refunded. The changed-quantity
  run pays 50. The stale receipt fails with `QuantityExceedsRemaining`; compare
  its before/after records to see that economic state was preserved.
- **Cancellation.** Inspect `transaction_results` for the failed buyer-only
  cancellation and the successful joint cancellation. The final PO is
  `Cancelled` with 56 paid and 44 refunded, leaving the contract balance at zero.
- **Hashes.** Both harnesses compare the WASM's size and SHA-256 with the
  build values before execution. Use the reported source revision and digest
  to identify the code and binary exercised. The checksum verifier separately
  checks the repository's recorded evidence files against their manifests.

These transaction hashes belong to the standalone ledger. The [public Testnet
flagship evidence](../evidence/testnet/) records a separate run using funded
Testnet identities, its own contract deployment and publicly queryable
transactions until the network resets. The local cancellation result establishes
behavior on protocol 28. See [evidence scope](EVIDENCE.md) for the recorded runs.
