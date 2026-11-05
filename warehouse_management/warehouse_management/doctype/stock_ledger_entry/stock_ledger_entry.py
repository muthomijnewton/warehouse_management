# Copyright (c) 2026, Newton Muthomi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Identity check: a value submitted through a request cannot reproduce this token.
LEDGER_WRITE_TOKEN = object()


class StockLedgerEntry(Document):
	def validate(self):
		if not self.is_new() or self.flags.stock_write_token is not LEDGER_WRITE_TOKEN:
			frappe.throw("Stock ledger entries are immutable and can only be created by stock transactions.")

	def on_trash(self):
		frappe.throw("Stock ledger entries cannot be deleted. Cancel the source Stock Entry instead.")

	def before_rename(self, old_name, new_name, merge=False):
		frappe.throw("Stock ledger entries cannot be renamed.")
