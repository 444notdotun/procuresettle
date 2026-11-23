#!/usr/bin/env python3
"""Tests for the offline receipt settlement calculator."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "calc-receipt-value.py"
FIXTURES = ROOT / "tests" / "fixtures"

SPEC = importlib.util.spec_from_file_location("calc_receipt_value", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
calculator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = calculator
SPEC.loader.exec_module(calculator)


def run_script(po_file: Path, receipt_file: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--po-file",
            str(po_file),
            "--receipt-file",
            str(receipt_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class SuccessfulCalculationTests(unittest.TestCase):
    def test_single_line_receipt(self) -> None:
        result = run_script(
            FIXTURES / "po-single-line.json", FIXTURES / "receipt-single-line.json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, re.compile(r"^1\s+Widgets\s+6\s+10\s+6\s+36$", re.M))
        self.assertIn("Total payout: 36", result.stdout)

    def test_multiple_lines_and_individual_payouts(self) -> None:
        result = run_script(
            FIXTURES / "po-multi-line.json", FIXTURES / "receipt-multi-line.json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, re.compile(r"^1\s+Widgets\s+6\s+10\s+6\s+36$", re.M))
        self.assertRegex(result.stdout, re.compile(r"^2\s+Gaskets\s+4\s+4\s+5\s+20$", re.M))
        self.assertIn("Total payout: 56", result.stdout)

    def test_delta_equal_to_remaining_quantity(self) -> None:
        result = run_script(
            FIXTURES / "po-multi-line.json", FIXTURES / "receipt-remaining-boundary.json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, re.compile(r"^2\s+Gaskets\s+4\s+4\s+5\s+20$", re.M))
        self.assertIn("Total payout: 20", result.stdout)

    def test_decimal_unit_price_is_exact(self) -> None:
        result = run_script(
            FIXTURES / "po-decimal-price.json", FIXTURES / "receipt-decimal-price.json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(
            result.stdout, re.compile(r"^1\s+.*\s+3\s+3\s+0\.125\s+0\.375$", re.M)
        )
        self.assertIn("Total payout: 0.375", result.stdout)
        self.assertNotIn("0.3750000000000000", result.stdout)

    def test_large_base_unit_price_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            po_file = write_json(
                directory,
                "po.json",
                [{"line_id": 1, "ordered_quantity": 2, "unit_price": "125000000"}],
            )
            receipt_file = write_json(
                directory,
                "receipt.json",
                {"receipt_id": 1, "quantities": [{"line_id": 1, "quantity_delta": 2}]},
            )
            result = run_script(po_file, receipt_file)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Total payout: 250000000", result.stdout)

    def test_amount_formatting_preserves_exactness(self) -> None:
        self.assertEqual(calculator.format_amount(Decimal("0.125") * 3), "0.375")
        self.assertEqual(calculator.format_amount(Decimal("6") * 6), "36")
        self.assertEqual(calculator.format_amount(Decimal("1E+8")), "100000000")


class ValidationFailureTests(unittest.TestCase):
    def test_delta_exceeds_remaining_quantity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt_file = write_json(
                directory,
                "receipt.json",
                {"receipt_id": 9, "quantities": [{"line_id": 2, "quantity_delta": 5}]},
            )
            result = run_script(FIXTURES / "po-multi-line.json", receipt_file)
        self.assertEqual(result.returncode, 1)
        self.assertIn("exceeds remaining quantity 4", result.stderr)
        self.assertNotIn("Total payout", result.stdout)

    def test_unmatched_receipt_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt_file = write_json(
                directory,
                "receipt.json",
                {"receipt_id": 9, "quantities": [{"line_id": 99, "quantity_delta": 1}]},
            )
            result = run_script(FIXTURES / "po-single-line.json", receipt_file)
        self.assertEqual(result.returncode, 1)
        self.assertIn("no matching PO line", result.stderr)
        self.assertNotIn("Total payout", result.stdout)

    def test_missing_input_file(self) -> None:
        result = run_script(
            FIXTURES / "not-present.json", FIXTURES / "receipt-single-line.json"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("file not found", result.stderr)
        self.assertNotIn("Total payout", result.stdout)

    def test_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            po_file = Path(directory) / "po.json"
            po_file.write_text("{not valid json", encoding="utf-8")
            result = run_script(po_file, FIXTURES / "receipt-single-line.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("malformed JSON", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_unit_prices(self) -> None:
        for price in (0, -1, "abc", None, True):
            with self.subTest(price=price):
                with tempfile.TemporaryDirectory() as directory:
                    po_file = write_json(
                        directory,
                        "po.json",
                        [{"line_id": 1, "ordered_quantity": 5, "unit_price": price}],
                    )
                    result = run_script(po_file, FIXTURES / "receipt-single-line.json")
                self.assertEqual(result.returncode, 1)
                self.assertIn("unit_price", result.stderr)
                self.assertNotIn("Total payout", result.stdout)

    def test_invalid_quantities_and_deltas(self) -> None:
        invalid_values = (0, -1, "1.5", None, True)
        for value in invalid_values:
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as directory:
                    receipt_file = write_json(
                        directory,
                        "receipt.json",
                        {"receipt_id": 1, "quantities": [{"line_id": 1, "quantity_delta": value}]},
                    )
                    result = run_script(FIXTURES / "po-single-line.json", receipt_file)
                self.assertEqual(result.returncode, 1)
                self.assertIn("quantity_delta", result.stderr)
                self.assertNotIn("Total payout", result.stdout)

    def test_duplicate_receipt_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt_file = write_json(
                directory,
                "receipt.json",
                {
                    "receipt_id": 1,
                    "quantities": [
                        {"line_id": 1, "quantity_delta": 1},
                        {"line_id": 1, "quantity_delta": 2},
                    ],
                },
            )
            result = run_script(FIXTURES / "po-single-line.json", receipt_file)
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate receipt line_id 1", result.stderr)

    def test_po_id_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt_file = write_json(
                directory,
                "receipt.json",
                {
                    "receipt_id": 1,
                    "po_id": 8,
                    "quantities": [{"line_id": 1, "quantity_delta": 1}],
                },
            )
            result = run_script(FIXTURES / "po-multi-line.json", receipt_file)
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match purchase order po_id 7", result.stderr)

    def test_missing_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            po_file = write_json(directory, "po.json", [{"line_id": 1, "ordered_quantity": 5}])
            result = run_script(po_file, FIXTURES / "receipt-single-line.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing required field 'unit_price'", result.stderr)

    def test_arguments_are_required(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--po-file", result.stderr)
        self.assertIn("--receipt-file", result.stderr)

    def test_help_documents_both_arguments(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--po-file", result.stdout)
        self.assertIn("--receipt-file", result.stdout)


def write_json(directory: str, name: str, data: object) -> Path:
    path = Path(directory) / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
