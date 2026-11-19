# Storage TTL and instance renewal

Soroban contract data has a Time-To-Live (TTL) measured in ledgers. When an
entry's TTL reaches zero the entry stops being live: persistent and instance
entries become **archived** and must be restored before they can be used again,
while temporary entries would be deleted permanently. ProcureSettle stores no
temporary data.

This page documents the renewal policy implemented in
[`contracts/po-settlement/src/lib.rs`](../contracts/po-settlement/src/lib.rs),
which calls renew each class of entry, and what integrators and operators
should expect when an entry is archived. It describes current behavior; it
does not change the policy. For the product-level boundary, see
[`docs/LIMITATIONS.md`](LIMITATIONS.md).

## Policy constants

Both constants are declared near the top of `lib.rs` (lines 9-15):

| Constant | Value | Meaning at the usual ~5 s ledger cadence |
| --- | --- | --- |
| `TTL_RENEW_THRESHOLD_LEDGERS` | `2_073_601` | about 120 days plus one ledger: bump only when fewer ledgers than this remain |
| `TTL_RENEW_TO_LEDGERS` | `2_592_000` | about 150 days: the target TTL after a bump |

These values are ledger counts, not wall-clock durations. The ~5 second close
time is a network setting, so the day equivalents are approximations.

`extend_ttl(threshold, extend_to)` is conditional: if the entry's current TTL
is **at least** `threshold`, the call is a no-op; otherwise the TTL is set to
`extend_to`. The contract therefore renews an entry at most once every
`2_592_000 - 2_073_601 = 518_399` ledgers (roughly 30 days) of progress,
instead of paying rent on every invocation.

The threshold sits one ledger above the currently documented network minimum
persistent TTL of `2_073_600` ledgers (~120 days), so a bump is requested as
soon as an entry would otherwise fall to the minimum. The 150-day target sits
below the currently documented maximum entry TTL of `3_110_400` ledgers
(~180 days). That margin matters because an `extend_to` above the network
maximum minus one causes the transaction to fail; a target below the ceiling
also avoids unnecessary rent. The TTL host tests configure the SDK host with
these same network values (`2_073_600` minimum, `3_110_400` maximum) so the
policy is exercised against realistic bounds rather than the SDK defaults.

Network TTL limits are configuration parameters and can change. The values
above were checked against the Stellar documentation on
[State Archival](https://developers.stellar.org/docs/learn/fundamentals/contract-development/storage/state-archival),
the resource-limits reference linked there, and
[CAP-46 State Archival Interface](https://github.com/stellar/stellar-protocol/blob/master/core/cap-0046-12.md)
on 2026-11-19. Re-check them before relying on the day equivalents; the
[Stellar Lab network limits](https://lab.stellar.org/network-limits) or the
network settings tooling report live values.

## What the contract stores

All purchase-order application data uses `env.storage().persistent()`:

- `DataKey::Header(po_id)` — the PO header and accounting fields
- `DataKey::Line(po_id, line_id)` — one ordered/priced PO line
- `DataKey::Receipt(po_id, receipt_id)` — one receipt identity and status
- `DataKey::ReceiptLine(po_id, receipt_id, line_id)` — one asserted quantity delta

Each of these persistent entries has its **own** TTL and must be extended by
key. The contract instance and the WASM code entry are separate ledger entries
with their own lifetimes; a single `env.storage().instance().extend_ttl(...)`
call extends the instance and (subject to an independent threshold check) the
code entry as well. The `MAX_LINES = 8` cap bounds how many line entries a
renewal loop can touch, so the number of entries bumped by any one call is
bounded.

Renewal is implemented by three helpers:

- `extend_contract_ttl` (`lib.rs:646-650`) calls `instance().extend_ttl` with
  the two constants.
- `extend_po_ttl` (`lib.rs:653-676`) checks that the header still exists,
  extends it, then extends every line listed in the header. It returns
  `NotFound` / `InvalidLine` if an expected entry is missing, so a PO can never
  be partially renewed.
- `extend_receipt_ttl` (`lib.rs:679-702`) does the same for a receipt and each
  receipt line indexed by that receipt, returning `ReceiptNotFound` /
  `InvalidReceipt` on a missing entry.

Newly created entries are extended immediately after they are written, so they
start at the 150-day target rather than the network minimum.

## Renewal on mutating calls

Every mutating entry point first calls `extend_contract_ttl`, keeping the
instance and code live. It then renews the persistent records that belong to
the state transition:

| Call | Instance / code | Persistent business records renewed |
| --- | --- | --- |
| `create_po` | yes | new header and every new PO line, extended right after `set` |
| `accept_po` | yes | existing header and all of its PO lines |
| `fund_po` | yes | existing header and all of its PO lines |
| `submit_receipt` | yes | header and all PO lines; new receipt and every new receipt line |
| `reject_receipt` | yes | header and all PO lines; receipt and all of its receipt lines |
| `accept_receipt_and_settle` | yes | header and all PO lines; receipt and all of its receipt lines |
| `cancel_po` | yes | header and all PO lines (no receipt records are needed) |

Renewing *all* lines rather than only the lines named in a receipt is
deliberate: the header and every line participate in quantity, conservation,
and closeout checks, so a later partial settlement must not find an untouched
line that has aged out.

TTL extensions are part of the same invocation as the state writes. If a
needed entry is missing the helpers fail the call, and if a later token
transfer fails, Soroban invocation atomicity rolls back the writes **and** the
TTL extensions together. Host tests assert the unchanged TTL values on both
outgoing-transfer failure paths.

## Why read-only getters do not renew business records

The four getters (`get_po`, `get_line`, `get_receipt`, `get_receipt_line`) and
the `receipt_value` preview call all call `extend_contract_ttl`, so a query
does keep the contract instance and code live. They deliberately do **not**
call `extend_po_ttl` / `extend_receipt_ttl` and do not issue any
`persistent().extend_ttl` calls: the header, line, receipt, and receipt-line
TTLs are unchanged by a read.

The reasons are scope and cost:

- A query does not advance PO state, so there is no coherent set of records to
  protect. A getter typically touches one key; bumping just that key would
  leave the rest of the PO at different TTLs without preserving the whole
  lifecycle.
- Rent is charged when a TTL actually extends, and it scales with entry size
  and the number of ledgers added. Bundling business-record renewal into the
  mutating transitions makes the fee payer fund the full, consistent set for a
  logical operation instead of charging every reader for partial upkeep.
- Keeping only the instance and code live is enough to keep the contract
  callable. Persistent data is then governed by its own activity: a PO that is
  only queried can still age out and need restoration.

Note that `extend_ttl` is an explicit resource operation even inside a getter.
Integrators should simulate the final transaction so the declared resources and
fees include any instance/code bump that actually fires.

## Archival and restoration

An entry is live while `current_ledger <= liveUntilLedger`; once the current
ledger is greater, it is archived (persistent/instance) or dead (temporary).
The consequences for ProcureSettle:

- A transaction that includes an **archived persistent key in its footprint
  without the key in the restore list fails during apply, before contract
  code runs**. Contract code cannot observe or handle an archived entry.
- An archived persistent entry cannot be re-created with the same key. It must
  be restored first; only after restoration can it be read, modified, or
  deleted.
- The contract instance and WASM code can archive independently. If either is
  archived, no invocation can load the contract to perform the bumps above.

Since Protocol 23, normal simulation (Stellar RPC `simulateTransaction`)
populates a transaction **restore list** when it sees accesses to archived
persistent or instance entries. The subsequent `InvokeHostFunction` operation
restores those entries before the host function executes, and normal rent and
fees apply. A manually assembled transaction that skips simulation and omits
the restore entries fails instead. Rare cases still use an explicit
`RestoreFootprintOp` — for example, to pay restoration fees from a keeper
account, or when automatic restoration would make the invocation too large.

Restoration returns an entry at the network **minimum** TTL (~120 days), not
the contract's 150-day target. Neither restoration nor an ordinary read/write
invocation extends TTL by itself; an entry's TTL changes only through a
contract `extend_ttl` call or an `ExtendFootprintTTLOp`. Therefore, after
restoring a PO record, the next successful *mutating* call is what lifts it
back to the policy target. A getter alone will not.

## Operational guidance

- Treat renewal as activity-dependent, not permanent storage. An idle PO,
  receipt, or even the deployed instance can eventually archive; the README
  and [`docs/LIMITATIONS.md`](LIMITATIONS.md) state the same boundary.
- Always simulate final invocations and use the simulation result when
  assembling and submitting transactions, so archived entries are restored
  automatically and rent/resource fees are declared.
- For POs that must survive long periods with no buyer or supplier activity,
  arrange an off-chain keeper to submit `ExtendFootprintTTLOp` for the header,
  line, receipt, and receipt-line keys (and, if needed, the instance and code
  keys). That operation uses a read-only footprint, must be the only operation
  in its transaction, and cannot bump already-archived entries — restore
  those first.
- Anyone may extend or restore an entry without authorization, and TTLs are
  not a security or expiry mechanism. Authorization and lifecycle rules in
  the contract remain the source of truth.

## Verification

The policy is covered by host tests in
[`contracts/po-settlement/src/test.rs`](../contracts/po-settlement/src/test.rs):

- `ttl_policy_covers_full_lifecycle_beyond_default_boundary_and_rebumps` runs
  the funded settlement lifecycle past unextended network bounds and checks
  that a later receipt re-bumps the header and every PO line.
- `ttl_getters_do_not_renew_business_records_but_active_write_does` advances
  entries below the threshold, confirms getters renew only instance/code, and
  confirms the following settlement restores all business-record TTLs to the
  target.
- The outgoing-transfer rollback tests confirm that failed token transfers
  leave both values and TTLs unchanged.

Reproduce with the repository-root checks:

```sh
cargo fmt --all -- --check
cargo test --workspace --locked
stellar contract build --locked --package procuresettle
```

## Sources

- [State Archival — Stellar Developer Docs](https://developers.stellar.org/docs/learn/fundamentals/contract-development/storage/state-archival)
- [Storage strategies — bump on access](https://developers.stellar.org/docs/build/guides/storage/storage-strategies)
- [CAP-46 State Archival Interface](https://github.com/stellar/stellar-protocol/blob/master/core/cap-0046-12.md)
- [Stellar Lab network limits](https://lab.stellar.org/network-limits)
