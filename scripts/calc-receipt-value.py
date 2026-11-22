#!/usr/bin/env python3
"""Calculate a receipt settlement payout offline from PO line prices.

The PO file uses the repository's ``LineInput`` shape (see
``schemas/examples/valid-po.json``): either a JSON array of line objects, or an
object with a ``lines`` array such as the output of ``scripts/inspect-po.py``.
The receipt file uses the ``ReceiptQuantityInput`` shape (see
``schemas/examples/valid-receipt.json``): an object with a ``quantities`` array.

Each line is matched by ``line_id``. A receipt delta must be positive and must
not exceed ``ordered_quantity - accepted_quantity``. The payout is
``delta * unit_price``; amounts are computed with ``decimal.Decimal`` so that
input prices are never approximated by binary floating-point arithmetic.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

MAX_LINES = 8
U64_MAX = 2**64 - 1
I128_MAX = 2**127 - 1

PO_ARRAY_KEYS = ("lines", "po_lines")
RECEIPT_ARRAY_KEYS = ("quantities", "lines")


class SettlementError(Exception):
    """An input or validation problem that makes the payout unreliable."""


@dataclass(frozen=True)
class PoLine:
    line_id: int
    ordered_quantity: int
    accepted_quantity: int
    unit_price: Decimal
    description: str


@dataclass(frozen=True)
class ReceiptLine:
    line_id: int
    quantity_delta: int


@dataclass(frozen=True)
class PayoutLine:
    line_id: int
    description: str
    quantity_delta: int
    remaining: int
    unit_price: Decimal
    value: Decimal


def load_json(path: Path, label: str) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle, parse_float=Decimal)
    except FileNotFoundError as exc:
        raise SettlementError(f"{label} file not found: {path}") from exc
    except OSError as exc:
        raise SettlementError(f"cannot read {label} file '{path}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SettlementError(
            f"malformed JSON in {label} file '{path}': line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def extract_array(data: Any, keys: tuple[str, ...], label: str) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in keys:
            if key in data:
                value = data[key]
                if isinstance(value, list):
                    return value
                raise SettlementError(f"{label} '{key}' must be a JSON array")
    raise SettlementError(f"{label} must be a JSON array or an object with a '{keys[0]}' array")


def parse_integer(value: Any, label: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise SettlementError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SettlementError(f"{label} must be an integer, got {value!r}") from exc
    if parsed < minimum or parsed > U64_MAX:
        raise SettlementError(f"{label} must be between {minimum} and {U64_MAX}")
    return parsed


def parse_quantity(value: Any, label: str, minimum: int = 1) -> int:
    return parse_integer(value, label, minimum)


def parse_price(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal, str)):
        raise SettlementError(f"{label} must be a positive number")
    try:
        price = Decimal(value) if isinstance(value, str) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SettlementError(f"{label} must be a positive number, got {value!r}") from exc
    if not price.is_finite() or price <= 0:
        raise SettlementError(f"{label} must be a finite positive number")
    return price


def optional_description(record: dict[str, Any]) -> str:
    for key in ("description", "item"):
        value = record.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise SettlementError(f"line {record.get('line_id')!r} '{key}' must be a string")
        return value
    return ""


def parse_po_lines(data: Any) -> dict[int, PoLine]:
    records = extract_array(data, PO_ARRAY_KEYS, "purchase order")
    if not records:
        raise SettlementError("purchase order contains no lines")
    if len(records) > MAX_LINES:
        raise SettlementError(f"purchase order has {len(records)} lines; maximum is {MAX_LINES}")

    lines: dict[int, PoLine] = {}
    for index, record in enumerate(records):
        label = f"purchase order line at index {index}"
        if not isinstance(record, dict):
            raise SettlementError(f"{label} must be a JSON object")
        for field in ("line_id", "ordered_quantity", "unit_price"):
            if field not in record:
                raise SettlementError(f"{label} is missing required field '{field}'")
        line_id = parse_integer(record["line_id"], f"{label} line_id")
        if line_id in lines:
            raise SettlementError(f"duplicate PO line_id {line_id}")
        ordered = parse_quantity(record["ordered_quantity"], f"line {line_id} ordered_quantity")
        accepted = parse_quantity(
            record.get("accepted_quantity", 0), f"line {line_id} accepted_quantity", minimum=0
        )
        if accepted > ordered:
            raise SettlementError(
                f"line {line_id} accepted_quantity {accepted} exceeds ordered_quantity {ordered}"
            )
        price = parse_price(record["unit_price"], f"line {line_id} unit_price")
        lines[line_id] = PoLine(
            line_id=line_id,
            ordered_quantity=ordered,
            accepted_quantity=accepted,
            unit_price=price,
            description=optional_description(record),
        )
    return lines


def parse_receipt_lines(data: Any) -> list[ReceiptLine]:
    records = extract_array(data, RECEIPT_ARRAY_KEYS, "receipt")
    if not records:
        raise SettlementError("receipt contains no lines")
    if len(records) > MAX_LINES:
        raise SettlementError(f"receipt has {len(records)} lines; maximum is {MAX_LINES}")

    lines: list[ReceiptLine] = []
    seen: set[int] = set()
    for index, record in enumerate(records):
        label = f"receipt line at index {index}"
        if not isinstance(record, dict):
            raise SettlementError(f"{label} must be a JSON object")
        for field in ("line_id", "quantity_delta"):
            if field not in record:
                raise SettlementError(f"{label} is missing required field '{field}'")
        line_id = parse_integer(record["line_id"], f"{label} line_id")
        if line_id in seen:
            raise SettlementError(f"duplicate receipt line_id {line_id}")
        delta = parse_quantity(record["quantity_delta"], f"line {line_id} quantity_delta")
        seen.add(line_id)
        lines.append(ReceiptLine(line_id=line_id, quantity_delta=delta))
    return lines


def check_po_ids(po_data: Any, receipt_data: Any) -> None:
    if not isinstance(po_data, dict) or not isinstance(receipt_data, dict):
        return
    header = po_data.get("header", po_data)
    if not isinstance(header, dict) or "po_id" not in header or "po_id" not in receipt_data:
        return
    po_id = parse_integer(header["po_id"], "purchase order po_id")
    receipt_po_id = parse_integer(receipt_data["po_id"], "receipt po_id")
    if po_id != receipt_po_id:
        raise SettlementError(
            f"receipt po_id {receipt_po_id} does not match purchase order po_id {po_id}"
        )


def calculate(lines: dict[int, PoLine], quantities: list[ReceiptLine]) -> tuple[list[PayoutLine], Decimal]:
    payouts: list[PayoutLine] = []
    total = Decimal(0)
    for quantity in quantities:
        line = lines.get(quantity.line_id)
        if line is None:
            raise SettlementError(f"receipt line {quantity.line_id} has no matching PO line")
        remaining = line.ordered_quantity - line.accepted_quantity
        if quantity.quantity_delta > remaining:
            raise SettlementError(
                f"line {quantity.line_id} delta {quantity.quantity_delta} exceeds remaining quantity {remaining}"
            )
        value = Decimal(quantity.quantity_delta) * line.unit_price
        if not value.is_finite() or value > I128_MAX:
            raise SettlementError(f"line {quantity.line_id} payout exceeds the i128 base-unit limit")
        total += value
        if total > I128_MAX:
            raise SettlementError("total payout exceeds the i128 base-unit limit")
        payouts.append(
            PayoutLine(
                line_id=line.line_id,
                description=line.description,
                quantity_delta=quantity.quantity_delta,
                remaining=remaining,
                unit_price=line.unit_price,
                value=value,
            )
        )
    return payouts, total


def format_amount(value: Decimal) -> str:
    return format(value.normalize(), "f")


def print_table(payouts: list[PayoutLine], total: Decimal) -> None:
    headers = ("Line", "Description", "Delta", "Remaining", "Unit price", "Payout")
    rows = [
        (
            str(payout.line_id),
            payout.description,
            str(payout.quantity_delta),
            str(payout.remaining),
            format_amount(payout.unit_price),
            format_amount(payout.value),
        )
        for payout in payouts
    ]
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]

    print("  ".join(header.ljust(width) for header, width in zip(headers, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        cells = [cell.ljust(width) for cell, width in zip(row, widths)]
        print("  ".join(cells).rstrip())
    print("")
    print(f"Total payout: {format_amount(total)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calculate an offline receipt settlement payout from PO line prices.",
        epilog=(
            "Example: python3 scripts/calc-receipt-value.py "
            "--po-file schemas/examples/valid-po.json "
            "--receipt-file schemas/examples/valid-receipt.json"
        ),
    )
    parser.add_argument(
        "--po-file",
        required=True,
        type=Path,
        metavar="PATH",
        help="path to the purchase order JSON file (LineInput lines, with optional accepted_quantity)",
    )
    parser.add_argument(
        "--receipt-file",
        required=True,
        type=Path,
        metavar="PATH",
        help="path to the receipt JSON file (receipt_id plus quantities with line_id and quantity_delta)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        po_data = load_json(args.po_file, "purchase order")
        receipt_data = load_json(args.receipt_file, "receipt")
        check_po_ids(po_data, receipt_data)
        po_lines = parse_po_lines(po_data)
        receipt_lines = parse_receipt_lines(receipt_data)
        payouts, total = calculate(po_lines, receipt_lines)
    except SettlementError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print_table(payouts, total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
