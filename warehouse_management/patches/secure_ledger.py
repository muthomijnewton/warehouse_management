"""Synchronize standard permissions and add ledger lookup indexes after model sync."""

import frappe
from frappe.permissions import reset_perms


def execute():
	reset_perms("Stock Ledger Entry")
	reset_perms("Stock Entry")
	frappe.db.add_index(
		"Stock Ledger Entry", ["item", "posting_date", "posting_time", "creation"], "item_posting"
	)
	frappe.db.add_index("Stock Ledger Entry", ["stock_entry"], "stock_entry_lookup")
