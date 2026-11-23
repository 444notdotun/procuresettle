# Soroban contract events

This page specifies the event vocabulary and positional payloads used by the
purchase-order lifecycle. Topics and data are Soroban SDK tuples: the order is
part of the interface and consumers should decode values by position. Monetary
values are signed `i128` token base units; identifiers are `u64` values and
addresses are Soroban `Address` values.

The contract currently emits `po_created`, `po_funded`, `po_refunded`, and
`receipt_submitted`. The remaining lifecycle entries are reserved schema
documentation for the corresponding transitions; consumers must not infer that
an event was emitted unless it is present in the transaction event stream.

## Event catalog

| Event | Emitting operation | Topics | Data |
| --- | --- | --- | --- |
| `po_created` | `create_po` | `("po_created", po_id)` | `(buyer, supplier, total_value)` |
| `po_accepted` | `accept_po` | `("po_accepted", po_id)` | `supplier` |
| `po_funded` | `fund_po` | `("po_funded", po_id)` | `(buyer, total_value)` |
| `receipt_submitted` | `submit_receipt` | `("receipt_submitted", po_id, receipt_id)` | `supplier` |
| `receipt_settled` | `accept_receipt_and_settle` | `("receipt_settled", po_id, receipt_id)` | `payout` |
| `po_cancelled` | `cancel_po` | `("po_cancelled", po_id)` | `refund` |
| `po_refunded` | `cancel_po` | `("po_refunded", po_id)` | `(buyer, refund)` |

For the event rows that carry an address, the value is the party recorded on
the PO. `payout` and `refund` are the amount settled or returned in the PO's
selected token, in base units.

## `po_funded`

Published by `fund_po` after the exact stored total has been transferred into
the contract and the PO header has been persisted as funded.

- Topics: `("po_funded", po_id)`
- Data: `(buyer, total_value)`

| Field         | Type      | Description                                     |
| ------------- | --------- | ----------------------------------------------- |
| `po_id`       | `u64`     | Identifier of the funded purchase order.        |
| `buyer`       | `Address` | Buyer recorded on the purchase order.           |
| `total_value` | `i128`    | Value transferred, in positive token base units. |

## `po_created`

Published by `create_po` after the PO header and line records have been
validated and persisted.

- Topics: `("po_created", po_id)`
- Data: `(buyer, supplier, total_value)`

The data tuple preserves the recorded parties and the exact sum of the stored
line values.

## `po_accepted`

The acceptance event schema identifies the supplier who accepted the draft.

- Topics: `("po_accepted", po_id)`
- Data: `supplier`

## `receipt_settled`

The settlement event schema identifies the receipt and its quantity-derived
payout.

- Topics: `("receipt_settled", po_id, receipt_id)`
- Data: `payout`

## `po_cancelled`

The cancellation event schema identifies the PO and the refund amount. An
accepted-but-unfunded PO has a zero refund; a funded PO reports the remaining
unpaid, unrefunded value.

- Topics: `("po_cancelled", po_id)`
- Data: `refund`

## `po_refunded`

Published by `cancel_po` after a successful transfer of the positive unpaid,
unrefunded balance to the recorded buyer. An accepted PO cancelled before
funding emits no refund event.

- Topics: `("po_refunded", po_id)`
- Data: `(buyer, refund)`

## `receipt_submitted`

Published by `submit_receipt` after the supplier assertion and its receipt lines
have been persisted.

- Topics: `("receipt_submitted", po_id, receipt_id)`
- Data: `supplier`

| Field        | Type      | Description                                       |
| ------------ | --------- | ------------------------------------------------- |
| `po_id`      | `u64`     | Identifier of the funded purchase order.          |
| `receipt_id` | `u64`     | Identifier of the newly submitted receipt.        |
| `supplier`   | `Address` | Supplier recorded on the purchase order.          |
