# Procurement and Stellar glossary

## Host Test

A Rust test that runs the contract in the Soroban SDK's in-process host
environment. It can exercise contract calls, storage, authorization, and
token transfers without a running Stellar network.

## Line Item

An entry on a purchase order with its own identifier, ordered quantity, and
unit price. ProcureSettle also tracks the cumulative accepted quantity for
each line.

## Milestone Escrow

An escrow model that releases predetermined amounts when agreed milestones
are approved. See [Quantity-Derived Settlement](#quantity-derived-settlement)
for the approach used by ProcureSettle.

## Partial Settlement

A payment for accepted quantities that leaves part of a funded purchase
order unpaid. Later receipts can settle additional quantities within the
order's remaining limits.

## Purchase Order (PO)

A buyer's order to a supplier specifying what is being purchased. In
ProcureSettle, the PO stores the parties, settlement asset, and line items,
which determine the total value.

## Quantity-Derived Settlement

Settlement that calculates each payout by multiplying each newly accepted
line quantity by its stored unit price and summing those amounts.

## Receipt

A supplier's record of delivered quantities against purchase-order lines.
The buyer accepts the receipt to record those quantities and release payment.

## Restoration

The ledger operation that returns archived contract state to live storage so
it can be used again. See [Storage TTL and renewal](STORAGE-TTL.md).

## SAC (Stellar Asset Contract)

A built-in Soroban contract that exposes a Stellar asset, such as XLM or an
issued asset, through the token interface used to fund and settle a PO.

## Standalone Network

A separate Stellar ledger used for local integration runs. This repository
uses Stellar Quickstart to run standalone proofs with a real ledger and RPC.

## State Archival

The process that moves expired persistent data, contract instances, and
contract code out of live ledger state. Archived entries require restoration
before a contract invocation can use them.

## Stroop

The smallest unit of XLM. One stroop is 0.0000001 XLM.

## TTL (Time-To-Live)

The remaining number of ledgers for which a Soroban storage entry stays
live. Extending its TTL moves its expiration to a later ledger.
