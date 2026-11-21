# Storage TTL and renewal

Soroban gives every contract data and code entry a time-to-live (TTL) measured
in ledgers. ProcureSettle uses the standard bump-on-access pattern so that an
actively used purchase order stays live, without claiming permanent storage.
TTL is a storage-lifecycle mechanism, not a business deadline or an
authorization control.

For protocol background, see the Stellar documentation on
[State Archival](https://developers.stellar.org/docs/learn/fundamentals/contract-development/storage/state-archival)
and [storage strategies](https://developers.stellar.org/docs/build/guides/storage/storage-strategies).

## TTL constants

The contract crate defines two public constants in
[`contracts/po-settlement/src/lib.rs`](../contracts/po-settlement/src/lib.rs)
(lines 9-15):

| Constant | Value | Meaning |
| --- | --- | --- |
| `TTL_RENEW_THRESHOLD_LEDGERS` | `2_073_601` | Renew when fewer than 120 days plus one ledger remain. |
| `TTL_RENEW_TO_LEDGERS` | `2_592_000` | Renewal target of 150 days. |

At the conventional ~5-second ledger close time, these values correspond to
roughly 120 and 150 days. Day figures are estimates: ledger close time and TTL
network parameters can change with protocol or network-setting upgrades.

Both constants are below the currently documented maximum entry TTL of
`3_110_400` ledgers (~180 days). They do not promise that an entry stays live
for 150 days of wall-clock time, only that a qualifying call raises its TTL to
that many ledgers.

`extend_ttl(threshold, extend_to)` is a conditional floor, not an unconditional
reset: if the entry's current TTL is at least `threshold`, the call is a no-op;
otherwise the TTL is raised to at least `extend_to`. Repeated calls on an
active entry therefore renew it at most once per roughly 30-day gap.

## What is renewed and when

All storage keys used by the contract (`Header`, `Line`, `Receipt`, and
`ReceiptLine`) are **persistent** entries. Each persistent entry has its own
independent TTL. The contract instance is a separate entry, and the Wasm code
entry behind it has its own TTL as well.

| Entry | Storage | Renewal path |
| --- | --- | --- |
| Contract instance and Wasm code | instance + code | `extend_contract_ttl()` runs at the start of every public function. `env.storage().instance().extend_ttl()` extends both the instance and the code entry, with an independent threshold check for each. |
| PO header (`DataKey::Header`) | persistent | Created and extended in `create_po`; renewed by `extend_po_ttl()` in `accept_po`, `fund_po`, `submit_receipt`, `reject_receipt`, `accept_receipt_and_settle`, and `cancel_po`. |
| PO lines (`DataKey::Line`) | persistent | Created and extended in `create_po`; `extend_po_ttl()` renews the header **and every line listed in the header**, including lines not touched by a partial receipt. The list is bounded by `MAX_LINES` (8). |
| Receipt (`DataKey::Receipt`) | persistent | Created and extended in `submit_receipt`; renewed by `extend_receipt_ttl()` in `reject_receipt` and `accept_receipt_and_settle`. |
| Receipt lines (`DataKey::ReceiptLine`) | persistent | Created and extended in `submit_receipt`; `extend_receipt_ttl()` renews each line indexed by the receipt. |

The two persistent-entry helpers verify that the header, lines, receipt, and
receipt lines still exist before calling `extend_ttl`, returning `NotFound` or
`ReceiptNotFound` if any indexed entry is missing.

For mutating calls, the instance/code bump is attempted at function entry,
before authentication and validation. The persistent-entry bumps follow
authentication and validation and occur before the related state writes and
token transfers. Soroban invocation atomicity rolls back TTL extensions along
with storage and token effects when an invocation fails; a failed settlement or
cancellation does not leave partially renewed state behind.

## Why read-only getters do not renew business records

The read-only functions `get_po`, `get_line`, `get_receipt`, `get_receipt_line`,
and `receipt_value` do **not** call `extend_po_ttl()` or
`extend_receipt_ttl()`. They leave the TTLs of PO, line, receipt, and
receipt-line entries untouched. They do still call `extend_contract_ttl()` at
entry, so an inspection call can renew the shared contract instance and code
entries when those entries are below the threshold.

This split is deliberate:

- Persistent entries are separate ledger entries with separate TTLs. Renewing
  each of them on every read would turn a read-only inspection into a
  multi-entry write with additional footprint and rent costs.
- Renewal of business records is tied to lifecycle activity: every successful
  state-changing call renews the records it depends on. This keeps rent usage
  proportional to actual PO progress rather than to the number of reads.
- TTL is not an access-control boundary. Anyone may extend an entry's TTL with
  an external `ExtendFootprintTTLOp`, so limiting getter-side bumps is a cost
  and resource policy, not a security guarantee.

`get_po`, `get_line`, `get_receipt`, `get_receipt_line`, and `receipt_value` are
therefore suitable for monitoring, preflight, and value previews without
changing business-record TTLs. A `receipt_value` preview remains advisory:
settlement rechecks current quantity bounds before paying.

## Archived entries and restoration

An entry is no longer live when the current ledger exceeds its
`liveUntilLedger`. Persistent and instance/code entries that expire are
**archived**, not deleted; a temporary entry would be deleted permanently, but
ProcureSettle does not use temporary storage. Archived persistent entries
cannot be re-created under the same key — they must be restored.

Contract code never executes against an archived entry:

- Since Protocol 23, a normal invocation whose simulation detects an archived
  entry adds that entry to the transaction's **restore list**. The network
  restores those entries before `InvokeHostFunction` runs, and normal rent and
  fees apply. Use the simulation result as-is when assembling and submitting
  the final transaction.
- A manually built transaction that omits required archived entries from its
  restore list fails before contract execution. Do not strip or replace the
  restore list produced by simulation.
- In rare cases, restoration can be done separately with `RestoreFootprintOp`
  (the CLI wraps this as `stellar contract restore`). Both the contract
  instance and its Wasm code may need restoration; they are distinct ledger
  keys. Archived PO, line, receipt, and receipt-line entries can be restored
  individually by key.
- A restored entry comes back at the network minimum TTL (currently
  `2_073_600` ledgers, about 120 days), not automatically at ProcureSettle's
  150-day target. A later successful lifecycle call, or an explicit TTL
  extension, raises it to the target.

Neither reads nor restoration alone extend TTLs beyond the restored minimum.
External TTL management remains available: `ExtendFootprintTTLOp` (the CLI wraps
this as `stellar contract extend`) can extend any live entry, is not restricted
to the contract's parties, and charges rent proportional to entry size and the
number of ledgers added. This makes keeper-based extension possible for POs
that must survive long periods of inactivity.

## Operational guidance

- Treat the 150-day target as activity-based, not as permanent storage. An idle
  PO can eventually archive.
- Always simulate the final transaction and preserve the simulation's restore
  list; retry restoration plus the original call when an archived entry is
  detected.
- If a PO must remain continuously available, arrange periodic lifecycle
  activity or external TTL extensions covering the header, all lines, and each
  live receipt and receipt line.
- Verify current minimum and maximum TTL network parameters before relying on
  the day-equivalent figures above.

The host tests `ttl_policy_covers_full_lifecycle_beyond_default_boundary_and_rebumps`
and `ttl_getters_do_not_renew_business_records_but_active_write_does` in
[`contracts/po-settlement/src/test.rs`](../contracts/po-settlement/src/test.rs)
cover renewal across the full lifecycle, re-bumping below the threshold,
getter behavior, and rollback on failed calls.
