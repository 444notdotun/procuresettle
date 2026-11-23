# ProcureSettle contract errors

The contract returns the following `PoError` codes. Read the current PO,
receipt, and line records before retrying a rejected operation.

| Code | Identifier | Cause | Caller action |
| ---: | --- | --- | --- |
| 1 | `AlreadyExists` | A PO with that ID already exists. | Read the existing PO to reconcile a replay, or choose a new nonzero ID for a different order. |
| 2 | `NotFound` | The requested PO header or a required stored PO line is missing. | Check the contract address, network, and identifiers. Restore archived entries before retrying when applicable. |
| 3 | `InvalidPoId` | PO creation used ID zero. | Supply a unique nonzero PO ID. |
| 4 | `InvalidLine` | A PO has no lines, a line ID or quantity is zero, a price is nonpositive, or a line reference is invalid. | Supply at least one valid line with a nonzero ID and quantity and a positive price in token base units. If the error references stored data, inspect the PO before retrying. |
| 5 | `DuplicateLineId` | Two input lines share a PO line ID. | Use a distinct line ID for each PO line. |
| 6 | `TooManyLines` | A PO exceeds the eight-line limit. | Use at most eight lines per PO. |
| 7 | `ArithmeticOverflow` | A checked calculation of a value, quantity, or accounting amount failed. | Use values whose products and totals fit the contract's integer types. If submitted inputs are already in range, inspect the stored accounting before retrying. |
| 8 | `InvalidParties` | The buyer and supplier are the same address. | Supply distinct buyer and supplier addresses. |
| 9 | `InvalidState` | The requested operation is invalid for the current PO status or the PO's accounting fails a consistency check. | Reload the PO and use a transition permitted by its current status. Investigate inconsistent accounting before retrying. |
| 10 | `ReceiptAlreadyExists` | The receipt ID is already in use on this PO. | Read the existing receipt to reconcile a replay, or use a new nonzero receipt ID for a different submission. |
| 11 | `InvalidReceipt` | A receipt has ID zero, an empty or oversized list of quantities, a zero line ID or quantity delta, or invalid stored receipt data. | Supply a nonzero ID and positive deltas on valid PO lines. Keep the number of receipt lines within the PO line count. Inspect existing receipt data if reading or settling it fails. |
| 12 | `DuplicateReceiptLine` | The same PO line is listed more than once in the receipt. | Combine deltas for that line into a single entry within its remaining quantity. |
| 13 | `UnknownPoLine` | A receipt refers to a line that is absent from the PO. | Read the PO's line IDs and use one of its existing lines. Check for archival when an expected line is missing. |
| 14 | `QuantityExceedsRemaining` | A receipt delta exceeds a line's current unaccepted quantity, or the stored accepted quantity already exceeds the order. | Refresh the line quantities. For a stale receipt, submit a new receipt with deltas within the remaining amounts. Investigate inconsistent stored quantities. |
| 15 | `InvalidReceiptState` | Settlement or rejection requires a submitted receipt, or a rejected receipt was queried for a settlement value. | Reload the receipt and choose an operation permitted for its status. Treat a settled receipt as already processed. |
| 16 | `ReceiptNotFound` | A receipt header or one of its required line records is missing. | Check the PO and receipt IDs, and restore archived records if applicable. |
| 17 | `SettlementExceedsFunded` | The calculated payment is nonpositive or cumulative payment would exceed the PO's funding or total value. | Refresh the PO and receipt, reconcile the funded and paid amounts, and investigate the discrepancy before retrying. |

Soroban authorization errors and token contract failures are reported
separately from these ProcureSettle codes. For example, funding requires
the recorded buyer to authorize the call and hold sufficient spendable tokens.

See [current limitations](LIMITATIONS.md) for the numeric model and storage
restoration context.
