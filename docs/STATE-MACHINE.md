# ProcureSettle state machine transition reference

This document defines the complete state machine transition matrices for
purchase orders (`PoStatus`) and receipts (`ReceiptStatus`) in ProcureSettle,
reflecting the contract rules in
[`contracts/po-settlement/src/lib.rs`](../contracts/po-settlement/src/lib.rs).

---

## 1. Purchase order state machine (`PoStatus`)

A purchase order transitions through discrete lifecycle stages from creation to
terminal completion or cancellation:

```
                  ┌───────────────┐
                  │ (Nonexistent) │
                  └───────┬───────┘
                          │ create_po [buyer auth]
                          ▼
                    ┌───────────┐
                    │   Draft   │
                    └─────┬─────┘
                          │ accept_po [supplier auth]
                          ▼
     cancel_po      ┌───────────┐
  ┌─────────────────┤ Accepted  │
  │ [buyer+supp]    └─────┬─────┘
  │                       │ fund_po [buyer auth]
  │                       ▼
  │  cancel_po      ┌───────────┐
  ├─────────────────┤  Funded   │◄──────────────┐
  │ [buyer+supp]    └─────┬─────┘               │ accept_receipt_and_settle
  │                       │                     │ (partial fulfillment)
  │                       │ accept_receipt_and_settle
  │                       │ (all lines fulfilled)
  ▼                       ▼
┌───────────┐       ┌───────────┐
│ Cancelled │       │  Closed   │
│(Terminal) │       │(Terminal) │
└───────────┘       └───────────┘
```

### Transition matrix

| Source State | Operation | Target State | Required Auth | Preconditions & Accounting Side Effects |
| --- | --- | --- | --- | --- |
| *(None)* | `create_po` | `Draft` | `buyer` | `po_id != 0`, `buyer != supplier`, 1 to 8 lines with `line_id != 0`, `ordered_quantity > 0`, `unit_price > 0`. Stores terms and emits `po_created` event. |
| `Draft` | `accept_po` | `Accepted` | `supplier` | PO must be in `Draft`. No token transfer. |
| `Accepted` | `fund_po` | `Funded` | `buyer` | PO must be `Accepted` and `funded_value == 0`. Transfers `total_value` of token from buyer to contract; sets `funded_value = total_value`. |
| `Accepted` | `cancel_po` | `Cancelled` | `buyer` AND `supplier` | PO must be `Accepted` with `funded_value == 0`, `paid_value == 0`, and `refunded_value == 0`. No tokens transferred. Terminal. |
| `Funded` | `accept_receipt_and_settle` | `Funded` | `buyer` | Receipt in `Submitted`; deltas fit remaining quantities; at least one line has `accepted_quantity < ordered_quantity` after settlement. Transfers settlement to supplier; increments `paid_value`. |
| `Funded` | `accept_receipt_and_settle` | `Closed` | `buyer` | Receipt in `Submitted`; all lines reach `accepted_quantity == ordered_quantity`; `paid_value == total_value`. Transfers settlement to supplier. Terminal. |
| `Funded` | `cancel_po` | `Cancelled` | `buyer` AND `supplier` | PO must be `Funded`; positive refund exists (`funded_value - paid_value - refunded_value > 0`). Transfers remaining unpaid tokens to buyer; sets `refunded_value`. Terminal. |

---

## 2. Purchase order terminal states

The terminal states for a purchase order are **`Closed`** and **`Cancelled`**.

### Allowed mutations: None

Once a purchase order enters a terminal state, **no further state mutations are permitted**:

| Terminal State | Attempted Operation | Required Auth | Outcome | Return Code |
| --- | --- | --- | --- | --- |
| `Closed` | `accept_po` | `supplier` | **Rejected** | `PoError::InvalidState` |
| `Closed` | `fund_po` | `buyer` | **Rejected** | `PoError::InvalidState` |
| `Closed` | `submit_receipt` | `supplier` | **Rejected** | `PoError::InvalidState` |
| `Closed` | `accept_receipt_and_settle` | `buyer` | **Rejected** | `PoError::InvalidState` |
| `Closed` | `cancel_po` | `buyer` + `supplier` | **Rejected** | `PoError::InvalidState` |
| `Cancelled` | `accept_po` | `supplier` | **Rejected** | `PoError::InvalidState` |
| `Cancelled` | `fund_po` | `buyer` | **Rejected** | `PoError::InvalidState` |
| `Cancelled` | `submit_receipt` | `supplier` | **Rejected** | `PoError::InvalidState` |
| `Cancelled` | `accept_receipt_and_settle` | `buyer` | **Rejected** | `PoError::InvalidState` |
| `Cancelled` | `cancel_po` | `buyer` + `supplier` | **Rejected** | `PoError::InvalidState` |

*Note: Read-only getters (`get_po`, `get_line`, `get_funded_value`) remain callable in terminal states.*

---

## 3. Purchase order rejected transitions

Attempting an operation outside its valid lifecycle state fails atomically with `PoError::InvalidState`:

| Current State | Attempted Operation | Expected State | Error Code | Reason |
| --- | --- | --- | --- | --- |
| `Draft` | `fund_po` | `Accepted` | `PoError::InvalidState` | Supplier must accept before funding. |
| `Draft` | `submit_receipt` | `Funded` | `PoError::InvalidState` | Cannot submit delivery deltas before PO is funded. |
| `Draft` | `accept_receipt_and_settle` | `Funded` | `PoError::InvalidState` | No funds deposited to settle. |
| `Draft` | `cancel_po` | `Accepted` or `Funded` | `PoError::InvalidState` | Cancellation requires mutual agreement on an accepted or funded order. |
| `Accepted` | `accept_po` | `Draft` | `PoError::InvalidState` | Order is already accepted. |
| `Accepted` | `submit_receipt` | `Funded` | `PoError::InvalidState` | Funding must be locked in escrow before receipts can be asserted. |
| `Accepted` | `accept_receipt_and_settle` | `Funded` | `PoError::InvalidState` | Cannot settle without escrow funding. |
| `Funded` | `accept_po` | `Draft` | `PoError::InvalidState` | Order already accepted and funded. |
| `Funded` | `fund_po` | `Accepted` | `PoError::InvalidState` | Order is already fully funded (`funded_value != 0`). |
| `Funded` | `create_po` (same ID) | *(None)* | `PoError::AlreadyExists` | Header already exists for this `po_id`. |

---

## 4. Receipt state machine (`ReceiptStatus`)

Receipts are scoped to a specific purchase order (`po_id`) and track delivery
assertions from submission to settlement or rejection:

```
                    ┌───────────────┐
                    │ (Nonexistent) │
                    └───────┬───────┘
                            │ submit_receipt [supplier auth]
                            ▼
                      ┌───────────┐
                      │ Submitted │
                      └─┬───────┬─┘
     reject_receipt     │       │ accept_receipt_and_settle
     [buyer auth]       │       │ [buyer auth]
                        ▼       ▼
                  ┌──────────┐ ┌─────────┐
                  │ Rejected │ │ Settled │
                  │(Terminal)│ │(Terminal│
                  └──────────┘ └─────────┘
```

### Transition matrix

| Source State | Operation | Target State | Required Auth | Preconditions & Side Effects |
| --- | --- | --- | --- | --- |
| *(None)* | `submit_receipt` | `Submitted` | `supplier` | PO must be `Funded`; `receipt_id != 0` and unique for this PO; `1 <= quantities.len() <= line_count`; every delta within line's remaining unaccepted quantity. |
| `Submitted` | `reject_receipt` | `Rejected` | `buyer` | Receipt must be in `Submitted` status. Rejection consumes `receipt_id` permanently. Terminal. |
| `Submitted` | `accept_receipt_and_settle` | `Settled` | `buyer` | Receipt must be `Submitted`; PO must be `Funded`; deltas still fit current remaining quantities. Advances `accepted_quantity` on PO lines and `paid_value` on PO header; transfers tokens to supplier. Terminal. |

---

## 5. Receipt terminal states

The terminal states for a receipt are **`Settled`** and **`Rejected`**.

### Allowed mutations: None

Once a receipt reaches a terminal state, **no further state mutations are permitted**:

| Terminal State | Attempted Operation | Required Auth | Outcome | Return Code |
| --- | --- | --- | --- | --- |
| `Settled` | `accept_receipt_and_settle` | `buyer` | **Rejected** | `PoError::InvalidReceiptState` |
| `Settled` | `reject_receipt` | `buyer` | **Rejected** | `PoError::InvalidReceiptState` |
| `Settled` | `submit_receipt` (same ID) | `supplier` | **Rejected** | `PoError::ReceiptAlreadyExists` |
| `Rejected` | `accept_receipt_and_settle` | `buyer` | **Rejected** | `PoError::InvalidReceiptState` |
| `Rejected` | `reject_receipt` | `buyer` | **Rejected** | `PoError::InvalidReceiptState` |
| `Rejected` | `submit_receipt` (same ID) | `supplier` | **Rejected** | `PoError::ReceiptAlreadyExists` |

*Note: Once a `receipt_id` is submitted, it can never be reused for another receipt on the same purchase order.*

### Read and query operations on receipts

| Operation | `Submitted` | `Settled` | `Rejected` |
| --- | --- | --- | --- |
| `receipt_value` | **Allowed** (advisory estimate; checks remaining bounds) | **Allowed** (recomputed exactly from immutable deltas & unit prices) | **Rejected** (`PoError::InvalidReceiptState`) |
| `get_receipt` | **Allowed** | **Allowed** | **Allowed** |
| `get_receipt_line` | **Allowed** | **Allowed** | **Allowed** |

---

## 6. Receipt rejected transitions

| Current State | Attempted Operation | Expected State | Error Code | Reason |
| --- | --- | --- | --- | --- |
| *(None)* | `reject_receipt` | `Submitted` | `PoError::ReceiptNotFound` | Receipt does not exist. |
| *(None)* | `accept_receipt_and_settle` | `Submitted` | `PoError::ReceiptNotFound` | Receipt does not exist. |
| `Rejected` | `receipt_value` | `Submitted` or `Settled` | `PoError::InvalidReceiptState` | Rejected assertions cannot be settled or valued. |
| `Rejected` | `accept_receipt_and_settle` | `Submitted` | `PoError::InvalidReceiptState` | Rejected receipts are permanently inactive. |
| `Settled` | `accept_receipt_and_settle` | `Submitted` | `PoError::InvalidReceiptState` | Cannot settle an already settled receipt. |
| `Settled` | `reject_receipt` | `Submitted` | `PoError::InvalidReceiptState` | Cannot reject an already settled receipt. |
