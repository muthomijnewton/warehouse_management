"""Explicit, operator-reviewed attestation of legacy valuation methods.

Run only after reconciling the item's complete historical ledger. No valuation
amounts, quantities, dates, or cancellation records are repaired by this helper.
"""

import frappe
from frappe import _

from warehouse_management.warehouse_management.doctype.stock_entry.stock_entry import METHODS


def confirm_valuation(item, method):
	if method not in METHODS:
		frappe.throw(_("Unsupported valuation method."))
	frappe.db.sql("SELECT name FROM `tabItem` WHERE name = %s FOR UPDATE", item)
	if not frappe.db.exists("Item", item):
		frappe.throw(_("Item {0} does not exist.").format(item))
	rows = frappe.db.sql(
		"SELECT name, stock_entry, reversal_of, valuation_method FROM `tabStock Ledger Entry` WHERE item = %s FOR UPDATE",
		item,
		as_dict=True,
	)
	reversed_names = {row.reversal_of for row in rows if row.reversal_of}
	for row in rows:
		if (
			frappe.db.get_value("Stock Entry", row.stock_entry, "docstatus") == 2
			and not row.reversal_of
			and row.name not in reversed_names
		):
			frappe.throw(
				_("Legacy cancellations need explicit reversal reconciliation before valuation attestation.")
			)
	if any(row.valuation_method and row.valuation_method != method for row in rows):
		frappe.throw(_("This method conflicts with an existing ledger method. Audit the history first."))
	frappe.db.sql(
		"""UPDATE `tabStock Ledger Entry` SET valuation_method = %s
		WHERE item = %s AND COALESCE(valuation_method, '') = ''""",
		(method, item),
	)
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Item",
			"reference_name": item,
			"content": f"Legacy valuation history attested as {method} by {frappe.session.user}.",
		}
	).insert(ignore_permissions=True)
	return {"item": item, "method": method, "reviewed_rows": len(rows)}
