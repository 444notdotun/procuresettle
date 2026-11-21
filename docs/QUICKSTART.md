# Quickstart: local development

Run these commands from the repository root. The pinned versions below come from
`rust-toolchain.toml`, `Cargo.toml`, and `.github/workflows/ci.yml`.

## Install the pinned toolchains

Rust 1.95.0 with rustfmt and the WASM target:

```sh
rustup toolchain install 1.95.0 --profile minimal --component rustfmt
rustup target add --toolchain 1.95.0 wasm32v1-none
rustc +1.95.0 --version
```

Stellar CLI 28.1.0 on Linux x86_64:

```sh
curl -fsSL -o stellar-cli.tar.gz \
  https://github.com/stellar/stellar-cli/releases/download/v28.1.0/stellar-cli-28.1.0-x86_64-unknown-linux-gnu.tar.gz
tar -xzf stellar-cli.tar.gz
sudo install -m 0755 stellar /usr/local/bin/stellar
stellar --version | head -1
```

For other platforms, use the [official Stellar CLI installation instructions](https://developers.stellar.org/docs/tools/developer-tools/cli/stellar-cli) and select version 28.1.0.

The local proof scripts also need Docker, `curl`, `jq`, and Python 3.11 or newer.
Their Python dependencies are pinned in `requirements-proof.txt`. On Debian or
Ubuntu, install `python3-venv` (for example `python3.12-venv`) if `python3 -m venv`
reports that `ensurepip` is unavailable.

## Build and test

```sh
cargo fmt --all -- --check
cargo test --workspace --locked
stellar contract build --locked --package procuresettle
python3 scripts/verify-evidence-checksums.py
```

Use `cargo fmt --all` to apply formatting before the check. The build produces
`target/wasm32v1-none/release/procuresettle.wasm`.

## Run the Docker-based local proofs

These proofs use a fresh protocol-28 standalone ledger, not Testnet or Mainnet.
The `flagship` job in `.github/workflows/ci.yml` is the authoritative setup
reference; it also retries Friendbot and confirms funded accounts through
Horizon.

```sh
export QUICKSTART_IMAGE_DIGEST=sha256:4f8dfd693deba57fddef7f0bc722e4782c2e606c8675e3adc5438cebae249295
export QUICKSTART_IMAGE_TAG=procuresettle-proof-4f8dfd693deb
export STELLAR_CONFIG_DIR="$PWD/.codex/stellar-config"
export REPORT_DIR="$PWD/.codex/reports"
mkdir -p "$STELLAR_CONFIG_DIR" "$REPORT_DIR"
docker pull "stellar/quickstart@$QUICKSTART_IMAGE_DIGEST"
docker tag "stellar/quickstart@$QUICKSTART_IMAGE_DIGEST" "stellar/quickstart:$QUICKSTART_IMAGE_TAG"
stellar --config-dir "$STELLAR_CONFIG_DIR" container start local \
  --name procuresettle-local-proof --cpus 2 --memory 4g \
  --protocol-version 28 --image-tag-override "$QUICKSTART_IMAGE_TAG"
stellar --config-dir "$STELLAR_CONFIG_DIR" network use local
until curl -fsS http://localhost:8000/health \
  | jq -e '.database_connected and .core_up and .core_synced' >/dev/null; do sleep 2; done
stellar --config-dir "$STELLAR_CONFIG_DIR" network info --network local | grep 'Protocol Version: 28'
```

Create three funded local identities, trust and distribute a test asset, and
deploy its Stellar Asset Contract:

```sh
for id in stage6-issuer stage6-buyer stage6-supplier; do
  stellar --config-dir "$STELLAR_CONFIG_DIR" keys generate "$id"
  address=$(stellar --config-dir "$STELLAR_CONFIG_DIR" keys public-key "$id")
  curl -fsS "http://localhost:8000/friendbot?addr=$address" >/dev/null
done
STAGE6_ISSUER=$(stellar --config-dir "$STELLAR_CONFIG_DIR" keys public-key stage6-issuer)
STAGE6_BUYER=$(stellar --config-dir "$STELLAR_CONFIG_DIR" keys public-key stage6-buyer)
STAGE6_SUPPLIER=$(stellar --config-dir "$STELLAR_CONFIG_DIR" keys public-key stage6-supplier)
ASSET="LSP:$STAGE6_ISSUER"
stellar --config-dir "$STELLAR_CONFIG_DIR" tx new change-trust \
  --source-account stage6-buyer --line "$ASSET" --network local
stellar --config-dir "$STELLAR_CONFIG_DIR" tx new change-trust \
  --source-account stage6-supplier --line "$ASSET" --network local
stellar --config-dir "$STELLAR_CONFIG_DIR" tx new payment \
  --source-account stage6-issuer --destination "$STAGE6_BUYER" \
  --asset "$ASSET" --amount 1000 --network local
STAGE6_SAC=$(stellar --config-dir "$STELLAR_CONFIG_DIR" contract asset deploy \
  --asset "$ASSET" --source-account stage6-issuer --network local)
```

Install the proof dependencies, then run both local scripts:

```sh
python3 -m venv .venv-proof
. .venv-proof/bin/activate
python -m pip install -r requirements-proof.txt
python3 scripts/local-flagship-proof.py \
  --config-dir "$STELLAR_CONFIG_DIR" \
  --wasm target/wasm32v1-none/release/procuresettle.wasm \
  --report-dir "$REPORT_DIR" \
  --issuer-identity stage6-issuer \
  --buyer-identity stage6-buyer --buyer-address "$STAGE6_BUYER" \
  --supplier-identity stage6-supplier --supplier-address "$STAGE6_SUPPLIER" \
  --sac-id "$STAGE6_SAC"
python3 scripts/local-cancellation-proof.py \
  --config-dir "$STELLAR_CONFIG_DIR" \
  --wasm target/wasm32v1-none/release/procuresettle.wasm \
  --report-dir "$REPORT_DIR" \
  --issuer-identity stage6-issuer \
  --buyer-identity stage6-buyer --buyer-address "$STAGE6_BUYER" \
  --supplier-identity stage6-supplier --supplier-address "$STAGE6_SUPPLIER" \
  --sac-id "$STAGE6_SAC"
```

Each script prints a summary with `"verdict": "PASS"` on success and writes its
raw transcript and summary to `$REPORT_DIR`. Stop the local network when done:

```sh
stellar --config-dir "$STELLAR_CONFIG_DIR" container stop procuresettle-local-proof
```

The Testnet scripts are intentionally not part of this local quickstart: they
submit public transactions and consume Testnet fees. See
[CONTRIBUTING.md](../CONTRIBUTING.md) before using them.
