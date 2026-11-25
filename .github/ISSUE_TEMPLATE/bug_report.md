---
name: Bug Report
about: Report a bug to help us improve
title: ''
labels: bug
assignees: ''
---

## Description

A clear and concise description of the bug. If this is about the smart contract behavior, say which entry point is affected (for example `create_po`, `submit_receipt`, `accept_receipt_and_settle`, `cancel_po`, or `receipt_value`).

## Steps to Reproduce

Provide the exact steps and inputs (PO IDs, line IDs, quantities, unit prices, receipt IDs) that trigger the bug.

1.
2.
3.

## Expected Behavior

What you expected to happen. If this is a contract behavior bug, state the expected status, state, or payout amount.

## Actual Behavior

What actually happened instead. Include the full error message or `PoError` code if one was returned (for example `Error(Contract, #14)`).

## Environment

- **Operating System**:
- **Rust Version** (output of `rustc --version`):
- **Soroban SDK Version** (see `Cargo.toml` / `Cargo.lock`):
- **Stellar CLI Version** (output of `stellar --version`):
- **Contract Version** (see `CHANGELOG.md` or the crate version in `contracts/po-settlement/Cargo.toml`):

## Additional Context

Optionally add logs, screenshots, CLI transcripts, transaction hashes, or any other information that might help diagnose the issue. If you are reporting a tooling or script problem, include the exact command you ran and where it failed.
