# Multi-line partial fulfillment

A buyer orders Cement, Steel, and Timber. Quantities count whole items, and
prices and balances below use the settlement token's smallest unit. In this
example, the contract holds funds for this PO only.

| Line ID | Item | Ordered quantity | Unit price | Line value |
| --- | --- | ---: | ---: | ---: |
| 1 | Cement (bags) | 10 | 120 | 10 × 120 = 1,200 |
| 2 | Steel (bars) | 8 | 250 | 8 × 250 = 2,000 |
| 3 | Timber (boards) | 12 | 75 | 12 × 75 = 900 |
| | **PO total** | | | **4,100** |

The supplier accepts the PO, then the buyer funds it by transferring the full
4,100 from their initial balance of 5,000 to the contract.

## Settle three receipts

The supplier submits each receipt with a positive quantity delta for each
delivered line and omits lines with no delivery. When the buyer accepts the
receipt through `accept_receipt_and_settle`, the contract checks each delta
against the line's remaining quantity, then sums each delta times its stored
unit price and transfers that payout to the supplier.

| Receipt | Delivery (quantity delta) | Payout calculation | Cumulative paid |
| --- | --- | ---: | ---: |
| 1 | 4 Cement, 3 Steel | (4 × 120) + (3 × 250) = **1,230** | 1,230 |
| 2 | 6 Cement, 5 Timber | (6 × 120) + (5 × 75) = **1,095** | 2,325 |
| 3 | 5 Steel, 7 Timber | (5 × 250) + (7 × 75) = **1,775** | 4,100 |

| After settlement | Cement accepted / remaining | Steel accepted / remaining | Timber accepted / remaining | PO status |
| --- | ---: | ---: | ---: | --- |
| Receipt 1 | 4 / 6 | 3 / 5 | 0 / 12 | `Funded` |
| Receipt 2 | 10 / 0 | 3 / 5 | 5 / 7 | `Funded` |
| Receipt 3 | 10 / 0 | 8 / 0 | 12 / 0 | `Closed` |

Receipt 3 fills all remaining quantities. With cumulative paid equal to the
4,100 funded total and zero refunded, the same settlement automatically
closes the PO.

## Token ledger balances

Each cell shows the balance after the step, with the change in parentheses.
After funding, the PO's remaining escrow is funded value minus cumulative paid
and refunded value. Refunded value stays at zero throughout this example.

| Step | Buyer | Contract | Supplier |
| --- | ---: | ---: | ---: |
| Before funding | 5,000 | 0 | 0 |
| Fund the PO | 900 (−4,100) | 4,100 (+4,100) | 0 (0) |
| Settle receipt 1 | 900 (0) | 2,870 (−1,230) | 1,230 (+1,230) |
| Settle receipt 2 | 900 (0) | 1,775 (−1,095) | 2,325 (+1,095) |
| Settle receipt 3 | 900 (0) | 0 (−1,775) | 4,100 (+1,775) |
