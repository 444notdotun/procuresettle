# Mutual cancellation and refund economics

`cancel_po` is a joint buyer-and-supplier operation. It is available only for
an `Accepted` or `Funded` purchase order, and the contract requires
authorization from both recorded parties before evaluating the cancellation.
The implementation is in [`contracts/po-settlement/src/lib.rs`](../contracts/po-settlement/src/lib.rs#L537-L605),
lines 537–605 in the cancellation implementation reference used for this
specification.

## Authorization

The buyer and supplier stored in the PO header each call `require_auth()`.
Therefore a buyer-only or supplier-only invocation cannot cancel the PO, even
if the other party agrees with the requested state transition. Authorization is
checked before any cancellation state is persisted or token is transferred.

## Accepted but unfunded POs

An `Accepted` PO has not moved settlement tokens into the contract. Cancellation
requires `funded_value`, `paid_value`, and `refunded_value` all to be zero, then
transitions the header to `Cancelled` without a token transfer. The economic
effect is consequently zero token movement: there is no escrow balance to
return.

## Funded and partially settled POs

For a `Funded` PO, the contract first checks that the full `total_value` was
funded and that the stored accepted line quantities recompute to `paid_value`.
The remaining refund is calculated as:

```text
refund = funded_value - paid_value - refunded_value
```

The result must be positive. The contract records the new cumulative
`refunded_value`, marks the PO `Cancelled`, and transfers only that remaining
amount from the contract to the recorded buyer. Thus a partially settled PO
returns the unpaid and not-yet-refunded portion; it does not reverse supplier
payouts that have already been made.

For example, a PO funded with 100 base units and already paid 56 has a refund
of 44 when no earlier refund exists. The accounting invariant after the refund
is `paid_value + refunded_value = funded_value`.

## Atomicity and failure behavior

The header is prepared and persisted before the outgoing token transfer so the
real cancellation path exercises Soroban invocation atomicity. If validation
fails, the state remains unchanged. If the refund transfer traps or otherwise
fails, the invocation rolls back the persisted cancellation state and refund
accounting together with the token-side effects. Callers should treat a failed
transaction as no cancellation having occurred and re-read the PO before
retrying.

This document describes the contract's accounting and authorization behavior;
it does not claim a public-network cancellation proof. The repository's
limitations page records the current local-ledger evidence boundary.
