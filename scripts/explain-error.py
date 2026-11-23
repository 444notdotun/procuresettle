#!/usr/bin/env python3
"""Decode ProcureSettle Soroban contract error codes into PoError descriptions.

Translates numeric contract error codes (1..=17) or raw Soroban CLI error
strings such as `HostError: Error(Contract, #5)` into the matching `PoError`
variant name, meaning, typical cause, and recommended fix.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class PoErrorInfo:
    code: int
    name: str
    meaning: str
    typical_cause: str
    recommended_fix: str


PO_ERRORS: dict[int, PoErrorInfo] = {
    1: PoErrorInfo(
        code=1,
        name="AlreadyExists",
        meaning="A purchase order with the specified `po_id` already exists in contract storage.",
        typical_cause="Calling `create_po` with a `po_id` that was already created earlier.",
        recommended_fix="Choose a new, unused `po_id` for `create_po`, or inspect the existing PO with `get_po`.",
    ),
    2: PoErrorInfo(
        code=2,
        name="NotFound",
        meaning="The referenced purchase order header or PO line does not exist in persistent storage.",
        typical_cause="Passing a non-existent `po_id` or `line_id`, or targeting a PO whose persistent entry expired and was archived.",
        recommended_fix="Verify `po_id` (and `line_id` for `get_line`) is correct; if inactive past TTL, restore the archived ledger entry first.",
    ),
    3: PoErrorInfo(
        code=3,
        name="InvalidPoId",
        meaning="The supplied `po_id` is invalid (`0` is reserved and disallowed).",
        typical_cause="Calling `create_po` with `po_id = 0`.",
        recommended_fix="Pass a positive, non-zero `u64` identifier for `po_id`.",
    ),
    4: PoErrorInfo(
        code=4,
        name="InvalidLine",
        meaning="The purchase order line list is empty or contains an invalid line definition.",
        typical_cause="Calling `create_po` with zero lines, or with a line where `line_id == 0`, `ordered_quantity == 0`, or `unit_price <= 0`.",
        recommended_fix="Provide at least one line item (up to 8) where `line_id > 0`, `ordered_quantity > 0`, and `unit_price > 0`.",
    ),
    5: PoErrorInfo(
        code=5,
        name="DuplicateLineId",
        meaning="Two or more lines in the purchase order share the same `line_id`.",
        typical_cause="Repeating a `line_id` value inside the `lines` vector passed to `create_po`.",
        recommended_fix="Assign a unique positive `line_id` to every line item in `create_po`.",
    ),
    6: PoErrorInfo(
        code=6,
        name="TooManyLines",
        meaning="The purchase order exceeds the maximum allowed number of line items (`MAX_LINES = 8`).",
        typical_cause="Passing more than 8 entries in `lines` when calling `create_po`.",
        recommended_fix="Reduce the purchase order to at most 8 lines, or split additional items across separate purchase orders.",
    ),
    7: PoErrorInfo(
        code=7,
        name="ArithmeticOverflow",
        meaning="An integer arithmetic operation overflowed or underflowed while calculating quantities or values.",
        typical_cause="Line value (`ordered_quantity * unit_price`), cumulative PO total, paid/refunded balance, or accepted quantity exceeded `i128`/`u64` bounds.",
        recommended_fix="Use smaller quantities or unit prices so every line value and cumulative total fits safely within positive `i128` limits.",
    ),
    8: PoErrorInfo(
        code=8,
        name="InvalidParties",
        meaning="The `buyer` and `supplier` addresses cannot be the same account.",
        typical_cause="Passing identical Stellar addresses for both `buyer` and `supplier` in `create_po`.",
        recommended_fix="Specify two distinct Stellar addresses for `buyer` and `supplier`.",
    ),
    9: PoErrorInfo(
        code=9,
        name="InvalidState",
        meaning="The purchase order is not in a lifecycle state that permits the requested operation.",
        typical_cause="Calling `accept_po` outside `Draft`, `fund_po` outside `Accepted`, `submit_receipt`/`accept_receipt_and_settle` outside `Funded`, or `cancel_po` on a `Draft`/`Closed`/`Cancelled` PO.",
        recommended_fix="Check the current PO status with `get_po` and follow the lifecycle order: `Draft` -> `accept_po` -> `fund_po` -> receipts/settlement (or `cancel_po` from `Accepted`/`Funded`).",
    ),
    10: PoErrorInfo(
        code=10,
        name="ReceiptAlreadyExists",
        meaning="A receipt with the given `(po_id, receipt_id)` already exists.",
        typical_cause="Reusing a `receipt_id` that was already submitted for this PO (including previously settled or rejected receipt IDs, which remain consumed).",
        recommended_fix="Submit the receipt with a new, unused `receipt_id` for this purchase order.",
    ),
    11: PoErrorInfo(
        code=11,
        name="InvalidReceipt",
        meaning="The receipt payload is malformed or violates receipt bounds.",
        typical_cause="Calling `submit_receipt` with `receipt_id == 0`, an empty `quantities` list, more lines than the PO contains, `line_id == 0`, or `quantity_delta == 0`.",
        recommended_fix="Pass a non-zero `receipt_id` and 1..=`line_count` entries, each with `line_id > 0` and `quantity_delta > 0`.",
    ),
    12: PoErrorInfo(
        code=12,
        name="DuplicateReceiptLine",
        meaning="A single receipt references the same PO `line_id` more than once.",
        typical_cause="Including duplicate `line_id` entries in the `quantities` vector passed to `submit_receipt`.",
        recommended_fix="Merge duplicate line quantities so each `line_id` appears at most once per receipt.",
    ),
    13: PoErrorInfo(
        code=13,
        name="UnknownPoLine",
        meaning="A receipt references a `line_id` that does not exist on the target purchase order.",
        typical_cause="Passing a `line_id` in `submit_receipt` that was not created with the PO.",
        recommended_fix="Inspect `line_ids` with `get_po` and reference only line IDs defined on that purchase order.",
    ),
    14: PoErrorInfo(
        code=14,
        name="QuantityExceedsRemaining",
        meaning="The receipt's `quantity_delta` exceeds the remaining unaccepted quantity on a PO line.",
        typical_cause="Submitting a delta larger than `ordered_quantity - accepted_quantity`, or settling a stale receipt after another receipt already consumed the remaining quantity.",
        recommended_fix="Check current `ordered_quantity` and `accepted_quantity` via `get_line`, then submit a new receipt within the remaining quantity.",
    ),
    15: PoErrorInfo(
        code=15,
        name="InvalidReceiptState",
        meaning="The receipt is not in a valid status for the invoked operation.",
        typical_cause="Attempting to settle or reject a receipt that is already `Settled` or `Rejected`, or calling `receipt_value` on a `Rejected` receipt.",
        recommended_fix="Check the receipt's `status` with `get_receipt`; only `Submitted` receipts can be settled or rejected, and `receipt_value` only supports `Submitted` or `Settled` receipts.",
    ),
    16: PoErrorInfo(
        code=16,
        name="ReceiptNotFound",
        meaning="No receipt or receipt line exists for the given `(po_id, receipt_id)`.",
        typical_cause="Passing an incorrect `po_id`, `receipt_id`, or `line_id`, calling before `submit_receipt` succeeded, or referencing an archived receipt entry.",
        recommended_fix="Verify `po_id`, `receipt_id` (and `line_id` for `get_receipt_line`) and ensure the receipt was submitted and is live.",
    ),
    17: PoErrorInfo(
        code=17,
        name="SettlementExceedsFunded",
        meaning="Settling the receipt would produce a non-positive payout or exceed the PO's funded/total value.",
        typical_cause="Attempting `accept_receipt_and_settle` when `paid_value + settlement_value > funded_value` (or `total_value`), or `settlement_value <= 0`.",
        recommended_fix="Inspect `funded_value`, `paid_value`, and `total_value` with `get_po`, and preview the payout with `receipt_value` before settling.",
    ),
}

CONTRACT_ERROR_RE = re.compile(r"Error\(\s*Contract\s*,\s*#(\d+)\s*\)", re.IGNORECASE)
NUMERIC_CODE_RE = re.compile(r"^#?(\d+)$")


def parse_error_code(raw: str) -> int | None:
    """Extract a numeric contract error code from a number or Soroban CLI error string."""
    text = raw.strip()
    if not text:
        return None
    direct_match = NUMERIC_CODE_RE.fullmatch(text)
    if direct_match is not None:
        return int(direct_match.group(1))
    cli_match = CONTRACT_ERROR_RE.search(text)
    if cli_match is not None:
        return int(cli_match.group(1))
    return None


def format_error(info: PoErrorInfo) -> str:
    return "\n".join(
        [
            f"#{info.code}: {info.name}",
            f"Meaning: {info.meaning}",
            f"Typical cause: {info.typical_cause}",
            f"Recommended fix: {info.recommended_fix}",
        ]
    )


def format_error_list() -> str:
    lines = ["ProcureSettle PoError codes (1..=17):"]
    for code in sorted(PO_ERRORS):
        info = PO_ERRORS[code]
        lines.append(f"  #{info.code:<2} {info.name:<26} {info.meaning}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="explain-error.py",
        description=(
            "Translate ProcureSettle Soroban contract error codes (1..=17) "
            "or raw CLI error messages into PoError details."
        ),
        epilog=(
            "examples:\n"
            "  python3 scripts/explain-error.py 5\n"
            "  python3 scripts/explain-error.py '#14'\n"
            "  python3 scripts/explain-error.py 'HostError: Error(Contract, #14)'\n"
            "  python3 scripts/explain-error.py --list"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "error",
        nargs="?",
        help="Contract error number (e.g. 5 or #14) or raw Soroban CLI error text.",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List all PoError codes (1..=17) with brief descriptions.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        print(format_error_list())
        return 0

    if args.error is None:
        parser.error("provide an error code (e.g. 5) or pass --list")

    code = parse_error_code(args.error)
    if code is None:
        print(
            f"Error: could not parse a Soroban contract error code from {args.error!r}. "
            "Expected a number (e.g. 5), '#5', or 'Error(Contract, #5)'.",
            file=sys.stderr,
        )
        return 1

    info = PO_ERRORS.get(code)
    if info is None:
        valid_min = min(PO_ERRORS)
        valid_max = max(PO_ERRORS)
        print(
            f"Error: unknown PoError code #{code} "
            f"(valid ProcureSettle PoError codes are {valid_min}..={valid_max}).",
            file=sys.stderr,
        )
        return 1

    print(format_error(info))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
