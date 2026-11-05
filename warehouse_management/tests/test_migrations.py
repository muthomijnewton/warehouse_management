"""Validation before legacy text columns are converted to numeric columns."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from warehouse_management.patches import validate_ledger_numbers


class TestLedgerMigration(FrappeTestCase):
	def test_valid_numeric_balances(self):
		row = frappe._dict(
			name="LEGACY", qty_after_transaction="2.500000000", stock_value_after_transaction="31.25"
		)
		with patch.object(frappe.db, "sql", return_value=[row]):
			validate_ledger_numbers.execute()

	def test_invalid_balances_fail_before_conversion(self):
		for value in (None, "", " ", "NaN", "Infinity", "1,000", "1_000", "1000000000000", "0.0000000001"):
			with self.subTest(value=value):
				row = frappe._dict(
					name="LEGACY", qty_after_transaction=value, stock_value_after_transaction="0"
				)
				with patch.object(frappe.db, "sql", return_value=[row]):
					with self.assertRaises(frappe.ValidationError):
						validate_ledger_numbers.execute()
