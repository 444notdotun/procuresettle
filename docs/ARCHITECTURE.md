# ProcureSettle architecture

ProcureSettle combines a Soroban purchase-order settlement contract with
off-chain verification tools and versioned execution evidence. The contract is
the source of settlement behavior; scripts and evidence make selected
calculations and executions reproducible and reviewable.

## Workspace structure

- `contracts/po-settlement/` contains the Rust Soroban contract crate. Its
  persistent PO, line, and receipt state and token transfers define the
  on-chain settlement lifecycle.
- `scripts/` contains supporting Python and shell tools. These include local
  and Testnet proof runners, input and receipt-value checks, repository
  validation, and evidence checksum verification.
- `evidence/` contains execution bundles grouped by scenario or run. Bundles
  preserve manifests, proof output, and, where applicable, transaction
  metadata and hashes.
- `docs/` describes the contract's data model and lifecycle, tool usage,
  evidence, limitations, and other project conventions.

The root Cargo workspace currently consists of the `procuresettle` contract
crate. GitHub Actions configuration is in `.github/workflows/`.

## On-chain contract and off-chain verification

The contract validates PO and receipt transitions, computes settlements from
buyer-accepted quantities and stored unit prices, and transfers the resulting
token amounts. Contract entry points and persistent state determine what
happens on ledger.

Off-chain scripts help prepare, run, or inspect verification without changing
that division of responsibility. For example, the receipt calculator
independently recomputes a value from JSON inputs, while proof scripts use the
Stellar CLI and RPC interfaces to exercise a contract on a local ledger or
Testnet. These tools provide reproducibility and checks; they do not enforce
contract rules or replace the contract's checks during settlement.

## Evidence bundles

Evidence bundles associate an execution with its recorded source revision,
toolchain and network details, contract artifact identity, results, and
transaction references when applicable. Local-ledger bundles preserve outputs
from isolated local executions; Testnet bundles additionally record public
transaction identifiers and the observed results. The network and execution
details vary by bundle, so each manifest is the source for that bundle's
specific provenance.

Each bundle includes `SHA256SUMS` for its files. Run
`python3 scripts/verify-evidence-checksums.py` to verify that the committed
files still match those recorded digests. The checksums establish the identity
and integrity of the preserved bytes; by themselves they do not prove that an
execution was correct, establish independent review, or guarantee that
historical Testnet data remains available. Read the bundle's manifest and
associated evidence record for the claims and limitations of each execution.

## CI verification

The `.github/workflows/ci.yml` workflow runs on pushes to and pull requests
against `main`. Its verification job checks repository hygiene, formatting,
Rust documentation, workspace tests, proof-script syntax and dry runs,
evidence checksums, and a locked contract build.

A separate hosted-proof job builds the contract and exercises the proof
scripts against a fresh local Stellar network using a pinned Quickstart image.
It checks the resulting execution evidence rather than treating a passing host
test as proof of ledger behavior. CI and committed evidence therefore serve
complementary purposes: CI checks a revision as it is proposed, while evidence
bundles retain the recorded details and outputs of selected runs.

For exact validation commands, proof reproduction instructions, and current
limitations, see [CONTRIBUTING.md](../CONTRIBUTING.md),
[docs/EVIDENCE.md](EVIDENCE.md), and
[docs/LIMITATIONS.md](LIMITATIONS.md).
