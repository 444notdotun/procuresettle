# ProcureSettle persistent storage data model

This specification documents the Soroban persistent storage architecture used by
ProcureSettle, including persistent keys (`DataKey`), contract struct fields,
storage layout, and the architectural rationale for granular entry separation.

All types and constants are defined in
[`contracts/po-settlement/src/lib.rs`](../contracts/po-settlement/src/lib.rs).

---

## 1. Storage architecture & `DataKey`

ProcureSettle uses Soroban's **persistent** storage durability (`env.storage().persistent()`)
for all business records. No temporary or instance storage is used for purchase
orders, line items, or receipts.

### Key definitions

The storage namespace is partitioned using the private `DataKey` enum:

```rust
#[contracttype]
#[derive(Clone)]
enum DataKey {
    Header(u64),
    Line(u64, u32),
    Receipt(u64, u64),
    ReceiptLine(u64, u64, u32),
}
```

| Variant | Key arguments | Stored value type | Purpose |
| --- | --- | --- | --- |
| `DataKey::Header` | `po_id: u64` | `PurchaseOrder` | Primary purchase order header, status, and accounting totals |
| `DataKey::Line` | `po_id: u64, line_id: u32` | `PoLine` | Individual line item terms and accepted progress |
| `DataKey::Receipt` | `po_id: u64, receipt_id: u64` | `Receipt` | Receipt submission metadata and status |
| `DataKey::ReceiptLine` | `po_id: u64, receipt_id: u64, line_id: u32` | `ReceiptLine` | Quantity delta asserted for a specific line item |

---

## 2. Granular storage rationale: bounding deserialization costs

Rather than storing line collections directly inside `PurchaseOrder` or `Receipt`
records as nested vectors, ProcureSettle separates each line into its own
discrete storage entry keyed by `(po_id, line_id)` and `(po_id, receipt_id, line_id)`.

### Why lines are stored as separate keys

1. **Bounding deserialization metering**:
   In the Soroban runtime, accessing or mutating a storage entry loads and
   deserializes the entire entry into WASM linear memory. Storage operations
   incur metering costs proportional to the entry's serialized byte size and CPU
   deserialization instructions.
2. **O(1) granular reads and writes**:
   During receipt settlement (`accept_receipt_and_settle`), each fulfilled line's
   `accepted_quantity` is updated individually. Writing to a specific
   `DataKey::Line(po_id, line_id)` requires serializing and writing only that
   line's small struct (`PoLine`), without rewriting the entire PO line collection.
3. **Preventing quadratic overhead on status checks**:
   Reading PO status, querying financial totals (`get_funded_value`), or
   performing lightweight lifecycle checks (`accept_po`, `fund_po`) only reads
   the `PurchaseOrder` header. Storing lines separately guarantees that header
   lookups never incur the deserialization footprint of lines.
4. **Bounded indexing via `line_ids`**:
   The header stores only a compact index `line_ids: Vec<u32>` bounded by
   `MAX_LINES = 8`. This gives callers deterministic enumerable indices for
   lifecycle verification, closeout validation, and preflight calculations
   without unboundedly growing the header footprint.

---

## 3. Data structures

### `PurchaseOrder`

The root header entity representing a purchase order agreement between a buyer
and a supplier.

```rust
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PurchaseOrder {
    pub po_id: u64,
    pub buyer: Address,
    pub supplier: Address,
    pub token: Address,
    pub status: PoStatus,
    pub total_value: i128,
    pub funded_value: i128,
    pub paid_value: i128,
    pub refunded_value: i128,
    pub line_count: u32,
    pub line_ids: Vec<u32>,
}
```

| Field | Type | Description |
| --- | --- | --- |
| `po_id` | `u64` | Caller-supplied unique PO identifier; must be non-zero and unused. |
| `buyer` | `Address` | Party that authorizes creation, funds escrow, and accepts/rejects receipts. |
| `supplier` | `Address` | Party that accepts the PO, submits receipts, and receives payouts. |
| `token` | `Address` | Address of the SEP-41 token used for escrow funding and settlement. |
| `status` | `PoStatus` | Current lifecycle status (`Draft`, `Accepted`, `Funded`, `Closed`, `Cancelled`). |
| `total_value` | `i128` | Checked sum of `ordered_quantity * unit_price` across all lines (positive token base units). |
| `funded_value` | `i128` | Amount transferred from buyer to contract upon funding (0 until funded, equals `total_value` once funded). |
| `paid_value` | `i128` | Cumulative sum of successfully settled payouts transferred to the supplier. |
| `refunded_value` | `i128` | Cumulative token value refunded to the buyer upon mutual cancellation. |
| `line_count` | `u32` | Number of distinct line items on this PO (bounded: `1 <= line_count <= MAX_LINES`). |
| `line_ids` | `Vec<u32>` | Bounded index of line IDs used for closeout checks, iteration, and preflight. |

#### Financial invariants
- **Funding**: When `status == PoStatus::Funded`, `funded_value == total_value`.
- **Settlement**: At all times, `paid_value == calculate_accepted_value()`.
- **Conservation**: When settled or cancelled, `paid_value + refunded_value <= funded_value`.

---

### `PoLine`

Represents an individual ordered item or service on a purchase order.

```rust
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PoLine {
    pub line_id: u32,
    pub ordered_quantity: u64,
    pub unit_price: i128,
    pub accepted_quantity: u64,
}
```

| Field | Type | Description |
| --- | --- | --- |
| `line_id` | `u32` | Positive nonzero unique identifier for the line within this PO. |
| `ordered_quantity` | `u64` | Total quantity ordered by the buyer; must be strictly positive (`> 0`). |
| `unit_price` | `i128` | Price per unit expressed in the token's integer base units; must be positive (`> 0`). |
| `accepted_quantity` | `u64` | Cumulative quantity accepted and settled by the buyer (initially `0`). |

#### Quantity invariant
- `accepted_quantity <= ordered_quantity`. Remaining quantity is derived as `ordered_quantity - accepted_quantity`.

---

### `Receipt`

Header for a supplier's delivery assertion against an active, funded purchase order.

```rust
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Receipt {
    pub receipt_id: u64,
    pub po_id: u64,
    pub status: ReceiptStatus,
    pub line_count: u32,
    pub line_ids: Vec<u32>,
}
```

| Field | Type | Description |
| --- | --- | --- |
| `receipt_id` | `u64` | Caller-supplied nonzero identifier unique to this PO; identity remains consumed even if rejected. |
| `po_id` | `u64` | Identifier of the parent purchase order. |
| `status` | `ReceiptStatus` | Current lifecycle state (`Submitted`, `Rejected`, `Settled`). |
| `line_count` | `u32` | Number of line deltas included in this receipt (`1 <= line_count <= header.line_count`). |
| `line_ids` | `Vec<u32>` | Bounded list of line IDs included in this receipt submission. |

---

### `ReceiptLine`

The specific quantity delta asserted for an individual line item in a receipt.

```rust
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReceiptLine {
    pub line_id: u32,
    pub quantity_delta: u64,
}
```

| Field | Type | Description |
| --- | --- | --- |
| `line_id` | `u32` | Nonzero identifier matching an existing line on the parent PO. |
| `quantity_delta` | `u64` | Positive quantity asserted delivered; bounded by remaining quantity at submission. |

---

## 4. Supporting input structures

These input types are provided as call arguments but are not stored directly in persistent storage:

- `LineInput`:
  - `line_id: u32`
  - `ordered_quantity: u64`
  - `unit_price: i128`
  Used in `create_po` to define initial line terms before conversion to `PoLine`.
- `ReceiptQuantityInput`:
  - `line_id: u32`
  - `quantity_delta: u64`
  Used in `submit_receipt` to provide delivery assertions before conversion to `ReceiptLine`.

---

## 5. Storage lifecycle and TTL coupling

All persistent entries created under `DataKey` are subject to Soroban's state archival rules:
- When any state mutation occurs on a PO (`create_po`, `accept_po`, `fund_po`, `accept_receipt_and_settle`, `cancel_po`), the helper `extend_po_ttl` iterates across `header.line_ids` to extend the TTL of the `Header` and every associated `Line` entry.
- When receipt operations occur (`submit_receipt`, `reject_receipt`, `accept_receipt_and_settle`), `extend_receipt_ttl` iterates across `receipt.line_ids` to extend the `Receipt` and all constituent `ReceiptLine` entries.
- This atomic extension ensures that related header and child entries never become partitioned by asymmetric TTL expiration.

See [`docs/STORAGE-TTL.md`](STORAGE-TTL.md) for the exact ledger thresholds (`TTL_RENEW_THRESHOLD_LEDGERS` and `TTL_RENEW_TO_LEDGERS`).
