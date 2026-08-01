# Copyright (c) 2026, Newton Muthomi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StockEntry(Document):
	def on_submit(self):
		if self.purpose == "Receipt":
			for row in self.items:
				self.create_ledger_entry(
					item=row.item,
					warehouse=row.target_warehouse,
					qty=row.quantity,
					rate=row.rate,
				)

	def create_ledger_entry(self, item, warehouse, qty, rate):
		ledger = frappe.new_doc("Stock Ledger Entry")

		ledger.posting_date = self.posting_date
		ledger.posting_time = self.posting_time
		ledger.item = item
		ledger.warehouse = warehouse
		ledger.stock_entry = self.name

		ledger.actual_quantity = qty
		ledger.valuation_rate = rate
		ledger.stock_value = qty * rate

		ledger.insert(ignore_permissions=True)

