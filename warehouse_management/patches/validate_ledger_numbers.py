"""Fail before schema conversion if legacy balances are not finite numbers."""

import re
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _


def execute():
	for row in frappe.db.sql(
		"""SELECT name, qty_after_transaction, stock_value_after_transaction
		FROM `tabStock Ledger Entry`""",
		as_dict=True,
	):
		for field in ("qty_after_transaction", "stock_value_after_transaction"):
			value = row[field]
			try:
				if value is None or not str(value).strip() or not Decimal(str(value)).is_finite():
					raise InvalidOperation
				if not re.fullmatch(
					r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", str(value).strip()
				):
					raise InvalidOperation
				number = Decimal(str(value))
				if number != number.quantize(Decimal("0.000000001")):
					raise InvalidOperation
				if abs(number) >= Decimal("1e12"):
					raise InvalidOperation
			except (InvalidOperation, ValueError):
				frappe.throw(
					_(
						"Ledger {0}: {1} must be a finite number below 1e12 in magnitude with at most nine decimal places. Audit and repair this legacy record before migrating; no value was guessed."
					).format(row.name, field)
				)
