# ProcureSettle FAQ

Frequently asked questions for developers building, testing, and integrating
ProcureSettle. Read [`/README.md`](../README.md) first for the implemented
flow, and see [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) for the overall
structure. For a quick environment setup, follow
[`docs/QUICKSTART.md`](QUICKSTART.md).

## Why is `MAX_LINES` capped at 8?

`MAX_LINES` is a conservative v0.1 invocation bound in `contracts/po-settlement/src/lib.rs`. The recorded reason is that each line uses a separate persistent entry, so the cap bounds caller input, duplicate-line checking, and total-value calculation. [`docs/LIMITATIONS.md`](LIMITATIONS.md) records the resulting rule: a purchase order can contain at most eight lines. The code and docs give no further rationale; this is a v0.1 limit, not a claim about a future configurable size.

## Does ProcureSettle support fractional quantities or decimal prices?

No. Quantities (`ordered_quantity`, `quantity_delta`, and `accepted_quantity`) are unsigned integers, and unit prices, totals, funding, payouts, and refunds are signed integers in the selected token's integer base units. `LineInput.unit_price` is documented as positive token base units per whole quantity unit, and settlement calculates `quantity_delta × unit_price` with checked integer arithmetic. There is no decimal quantity scale, currency conversion, tax, fee, discount, shipping, quality adjustment, or tolerance calculation. Any human-readable decimal rendering is therefore a client concern; the contract does not convert or format amounts. See [`docs/LIMITATIONS.md`](LIMITATIONS.md) and [`docs/DECIMALS.md`](DECIMALS.md).

## How does quantity-derived settlement differ from milestone escrow?

Generic milestone escrow releases predetermined amounts. ProcureSettle stores ordered quantities and unit prices instead of milestone amounts: `create_po` records the line terms and derives the total, `fund_po` transfers that exact total into the contract, and `submit_receipt` records the supplier's asserted per-line quantity deltas without paying them. `accept_receipt_and_settle` then requires the recorded buyer's authorization, rechecks the currently remaining quantities, derives the payout from each newly accepted delta at its stored unit price, increments the accepted quantities, and transfers only that value to the supplier. `receipt_value` provides a read-only preview, and final full acceptance closes the PO. The preview is advisory: settlement recomputes the payout from live state, so a stale receipt can fail with `QuantityExceedsRemaining` while leaving token balances unchanged. See [`docs/LIMITATIONS.md`](LIMITATIONS.md) and the README's receipt-preflight section.

## Can purchase orders be amended after acceptance?

No. `PoStatus` has only `Draft`, `Accepted`, `Funded`, `Closed`, and `Cancelled`, and the contract has no amendment entrypoint or path to change stored line terms, prices, or parties after creation. Both the README and [`docs/LIMITATIONS.md`](LIMITATIONS.md) state that there is no PO amendment in v0.1. An `Accepted` or `Funded` PO can instead be cancelled jointly by its recorded buyer and supplier through `cancel_po`; a funded PO refunds only its remaining unpaid, unrefunded value. The PO status has no transition out of `Closed` or `Cancelled`, so changing the commercial terms means cancelling where allowed and creating a new PO.

## What token standards are supported?

The contract calls the Soroban token interface through `token::TokenClient` for the `transfer` calls used when funding, settling, and refunding. The host tests use the pinned `soroban-sdk` test host and its Stellar Asset Contract fixture (`register_stellar_asset_contract_v2`). The recorded local-ledger and Testnet proofs use classic Stellar assets wrapped as Stellar Asset Contracts. Broad compatibility with arbitrary custom SEP-41 tokens has not been established; issuer behavior and asset policy remain external assumptions. See [`docs/LIMITATIONS.md`](LIMITATIONS.md) and [`docs/TOKEN-COMPATIBILITY.md`](TOKEN-COMPATIBILITY.md). The contract does not read or convert token decimals; amounts are handled in the token's integer base units.

## What toolchain versions does the repository require, and how do I set up local Rust and Soroban compilation?

The repository pins Rust and Cargo to **1.95.0** in
[`rust-toolchain.toml`](../rust-toolchain.toml) (with the `wasm32v1-none`
target), `soroban-sdk` **28.0.0** in `Cargo.toml` and `Cargo.lock`, and
**Stellar CLI 28.1.0** for contract builds and the CLI proof scripts. Python
3.11 or newer is only needed for the proof harnesses. To install the pinned
toolchain and target:

```sh
rustup toolchain install 1.95.0 --profile minimal --component rustfmt --component clippy
rustup target add --toolchain 1.95.0 wasm32v1-none
```

Install Stellar CLI 28.1.0 using the [official Stellar CLI installation
instructions](https://developers.stellar.org/docs/tools/developer-tools/cli/stellar-cli)
and confirm the first line of `stellar --version` reports `28.1.0`. Then build
the contract from the repository root:

```sh
stellar contract build --locked --package procuresettle
```

The build produces `target/wasm32v1-none/release/procuresettle.wasm`. The full
setup steps, including the pinned Quickstart image for local-ledger proofs, are
in [`CONTRIBUTING.md`](../CONTRIBUTING.md) and
[`docs/QUICKSTART.md`](QUICKSTART.md). If setup fails, see
[`docs/TROUBLESHOOTING.md`](TROUBLESHOOTING.md) for the common problems and
their fixes.

## How do I run the unit tests, and how do I interpret a test failure?

The host tests live in `contracts/po-settlement/src/test.rs` and run in-process
with the SDK's `testutils` feature, so no network, ledger, or Docker is
involved. Run them from the repository root with:

```sh
cargo test --workspace --locked
```

Each test starts from a fresh `fixture()` that generates buyer, supplier, and
issuer addresses, registers a Stellar Asset Contract token, and registers the
ProcureSettle contract, so tests share no state. A test failure usually means
one of the explicit assertions failed: state or token balances did not move as
expected, the wrong party would have had to sign (the `authorized_*` helpers
use exact `mock_auths`), a rejected call left partial state behind, or an
expected error code was wrong. Calculate expected values independently of the
contract (the tests use `independently_calculate_receipt_value` and
`independently_calculate_accepted_value` or literal numbers).

Running the tests also makes `soroban-sdk` write generated environment
snapshots to `contracts/po-settlement/test_snapshots/`. These are Git-ignored,
must not be committed, and there is no `insta` step in this project. Do not
weaken an existing assertion or accept a snapshot to make an unexpected failure
pass; fix the code or the test instead. See
[`CONTRIBUTING.md`](../CONTRIBUTING.md) for the full testing guidelines.

## What are the common build and compilation errors?

The most common problems are documented in detail in
[`docs/TROUBLESHOOTING.md`](TROUBLESHOOTING.md):

- **`error[E0463]: can't find crate for core`** when building for WASM: the
  `wasm32v1-none` target is not installed for the pinned toolchain. Fix with
  `rustup target add --toolchain 1.95.0 wasm32v1-none`.
- **`stellar: command not found`**: Stellar CLI 28.1.0 is not installed or its
  directory is not on your `PATH`. Install it and confirm `stellar --version`.
- **Formatting failures**: run `cargo fmt --all` before `cargo fmt --all -- --check`.
- **`cargo test` or build failures caused by toolchain drift**: the repository
  pins its versions and uses `--locked`, so use the pinned toolchain from
  `rust-toolchain.toml` instead of a newer or different Rust release.

Because the project pins exact versions in `rust-toolchain.toml`, `Cargo.toml`,
and `Cargo.lock`, most environment-mismatch errors come from using a different
Rust, SDK, or CLI version than the pinned ones.

## How do I interpret the contract error codes?

The contract returns `PoError` codes when validation or a lifecycle rule fails.
Codes start at `AlreadyExists` (1) and run to `SettlementExceedsFunded` (17);
for example, `InvalidState` (9) means the requested operation is not valid for
the current PO or receipt status, and `QuantityExceedsRemaining` (14) means a
receipt delta no longer fits the line's remaining quantity. The complete table
of codes, causes, and recommended caller actions is in
[`docs/ERRORS.md`](ERRORS.md). A common mistake is to retry without reading the
stored PO, receipt, and line records first; most codes are resolved by
inspecting current state and picking a transition permitted by it.

Soroban authorization failures and token contract failures are reported
separately from these codes. For example, `fund_po` requires the recorded
buyer to authorize the call and to hold enough spendable tokens; if
`require_auth()` fails, the host aborts the invocation rather than returning a
`PoError`. See [`docs/TOKEN-COMPATIBILITY.md`](TOKEN-COMPATIBILITY.md) for the
token-side behavior the contract depends on.

## How does storage TTL renewal work, and what should I know about gas and resources?

Every Soroban entry has a time-to-live measured in ledgers, and ProcureSettle
uses the standard bump-on-access pattern. `extend_contract_ttl()` runs at the
start of every public function and renews the contract instance and Wasm code.
Mutating calls additionally renew the PO header, every PO line, and (where
applicable) the receipt and receipt-line entries through `extend_po_ttl()` and
`extend_receipt_ttl()`. The constants are `TTL_RENEW_THRESHOLD_LEDGERS`
(`2_073_601`) and `TTL_RENEW_TO_LEDGERS` (`2_592_000`), so a qualifying call
raises an entry's TTL to roughly 150 days and a renewal happens at most once
per ~518,399 ledgers of progress instead of on every invocation. These are
ledger counts, not wall-clock promises.

Read-only getters and `receipt_value` intentionally do **not** renew PO or
receipt entries, so inspecting a PO does not grow its footprint or rent; this
is a resource policy, not a security guarantee. Resource usage is also bounded
by the data model: each of the at most `MAX_LINES` (8) lines is a separate
persistent entry, and the contract's loops are bounded by the recorded line
counts. The contract performs checked integer arithmetic throughout, and
`[profile.release]` enables `overflow-checks`.

An entry archives after its TTL expires without renewal. Contract code can
never observe an archived entry directly; a normal invocation whose simulation
detects one adds it to the transaction's restore list, so preserved simulation
results restore the archived entries before the contract runs. Manual
restoration is also possible with the CLI (`stellar contract restore`). After
restoration an entry returns at the network-minimum TTL and needs a later
mutating lifecycle call (or an explicit TTL extension) to reach the 150-day
target. TTL is a storage-lifecycle mechanism, not a business deadline, an
expiry, or an access-control boundary: anyone can extend or restore entries.
See [`docs/STORAGE-TTL.md`](STORAGE-TTL.md) for the constants, renewal policy,
archival, and restoration details.
