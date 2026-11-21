#!/usr/bin/env python3
"""Generate deterministic mock purchase-order JSON for LineInput fixtures."""

import argparse
import json
import sys
from pathlib import Path


def positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def line_count(value: str) -> int:
    parsed = positive_integer(value)
    if parsed > 8:
        raise argparse.ArgumentTypeError("must be between 1 and 8")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate mock purchase-order LineInput JSON fixtures.",
    )
    parser.add_argument(
        "--lines",
        type=line_count,
        default=3,
        metavar="COUNT",
        help="number of lines to generate (1-8; default: 3)",
    )
    parser.add_argument(
        "--price",
        type=positive_integer,
        default=100,
        metavar="BASE_UNITS",
        help="positive unit price in integer token base units (default: 100)",
    )
    parser.add_argument(
        "--qty",
        type=positive_integer,
        default=10,
        metavar="QUANTITY",
        help="positive ordered quantity for each line (default: 10)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help="write JSON to PATH instead of stdout",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    fixture = [
        {
            "line_id": line_id,
            "ordered_quantity": args.qty,
            "unit_price": str(args.price),
        }
        for line_id in range(1, args.lines + 1)
    ]
    rendered = json.dumps(fixture, indent=2) + "\n"

    if args.output is not None:
        try:
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            parser.error(f"could not write --output file '{args.output}': {exc}")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
