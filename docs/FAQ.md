# ProcureSettle FAQ

## Why is `MAX_LINES` capped at 8?

`MAX_LINES` is a conservative v0.1 invocation bound in `contracts/po-settlement/src/lib.rs`. The recorded reason is that each line uses a separate persistent entry, so the cap bounds caller input, duplicate-line checking, and total-value calculation. [`docs/LIMITATIONS.md`](LIMITATIONS.md) records the resulting rule: a purchase order can contain at most eight lines. The code and docs give no further rationale; this is a v0.1 limit, not a claim about a future configurable size.

## Does ProcureSettle support fractional quantities or decimal prices?

No. Quantities (`ordered_quantity`, `quantity_delta`, and `accepted_quantity`) are unsigned integers, and unit prices, totals, funding, payouts, and refunds are signed integers in the selected token's integer base units. `LineInput.unit_price` is documented as positive token base units per whole quantity unit, and settlement calculates `quantity_delta × unit_price` with checked integer arithmetic. There is no decimal quantity scale, currency conversion, tax, fee, discount, shipping, quality adjustment, or tolerance calculation. Any human-readable decimal rendering is therefore a client concern; the contract does not convert or format amounts. See [`docs/LIMITATIONS.md`](LIMITATIONS.md).

## How does quantity-derived settlement differ from milestone escrow?

Generic milestone escrow releases predetermined amounts. ProcureSettle stores ordered quantities and unit prices instead of milestone amounts: `create_po` records the line terms and derives the total, `fund_po` transfers that exact total into the contract, and `submit_receipt` records the supplier's asserted per-line quantity deltas without paying them. `accept_receipt_and_settle` then requires the recorded buyer's authorization, rechecks the currently remaining quantities, derives the payout from each newly accepted delta at its stored unit price, increments the accepted quantities, and transfers only that value to the supplier. `receipt_value` provides a read-only preview, and final full acceptance closes the PO. See [`docs/LIMITATIONS.md`](LIMITATIONS.md).

## Can purchase orders be amended after acceptance?

No. `PoStatus` has only `Draft`, `Accepted`, `Funded`, `Closed`, and `Cancelled`, and the contract has no amendment entrypoint or path to change stored line terms, prices, or parties after creation. Both the README and [`docs/LIMITATIONS.md`](LIMITATIONS.md) state that there is no PO amendment in v0.1. An `Accepted` or `Funded` PO can instead be cancelled jointly by its recorded buyer and supplier through `cancel_po`; a funded PO refunds only its remaining unpaid, unrefunded value. The PO status has no transition out of `Closed` or `Cancelled`, so changing the commercial terms means cancelling where allowed and creating a new PO.

## What token standards are supported?

The contract calls the Soroban token interface through `token::TokenClient` for the `transfer` calls used when funding, settling, and refunding. The host tests use the pinned `soroban-sdk` test host and its Stellar Asset Contract fixture (`register_stellar_asset_contract_v2`). The recorded local-ledger and Testnet proofs use classic Stellar assets wrapped as Stellar Asset Contracts. Broad compatibility with arbitrary custom SEP-41 tokens has not been established; issuer behavior and asset policy remain external assumptions. See [`docs/LIMITATIONS.md`](LIMITATIONS.md).
