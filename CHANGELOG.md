# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] - 2026-11-06

### Added

- Purchase-order creation by the buyer with per-line ordered quantities and
  unit prices (`create_po`), supplier acceptance (`accept_po`), and full
  funding of the PO by the buyer (`fund_po`).
- Quantity-derived receipt submission by the supplier (`submit_receipt`), with
  buyer rejection (`reject_receipt`) and a read-only value preflight
  (`receipt_value`).
- Buyer acceptance and settlement of a receipt (`accept_receipt_and_settle`),
  which rechecks current quantity bounds and transfers the exact
  quantity-derived amount to the supplier. The PO closes automatically once
  every ordered quantity is accepted.
- Mutual cancellation of an Accepted or Funded PO with buyer and supplier
  authorization (`cancel_po`); a Funded PO refunds only its remaining unpaid
  value to the buyer.
- TTL renewal policy: active contract calls renew the contract instance/code
  and the relevant live PO, line, receipt, and receipt-line entries to a
  bounded TTL window.
- Compatibility with the Soroban 28 SDK (`soroban-sdk` 28.0.0, pinned in
  `Cargo.toml`).
