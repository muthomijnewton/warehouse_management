"""CI-only disposable-site migration checks. Never run prepare on a live site."""

import frappe
from frappe import _

from warehouse_management.legacy_audit import confirm_valuation

ITEM = "UPGRADE-SMOKE-ITEM"
WAREHOUSE = "Upgrade Smoke Warehouse"


def prepare():
	if frappe.local.site != "upgrade.localhost":
		frappe.throw(_("This destructive fixture is restricted to the disposable upgrade.localhost site."))
	if not frappe.db.exists("UOM", "Piece"):
		frappe.get_doc({"doctype": "UOM", "unit_name": "Piece"}).insert()
	frappe.get_doc(
		{"doctype": "Item", "item_code": ITEM, "item_name": ITEM, "unit": "Piece", "valuation_method": "FIFO"}
	).insert()
	frappe.get_doc(
		{
			"doctype": "Warehouse",
			"warehouse_name": WAREHOUSE,
			"warehouse_code": "UPGRADE-SMOKE",
			"is_group": 0,
		}
	).insert()
	entry = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"purpose": "Receipt",
			"posting_date": "2026-01-01",
			"posting_time": "00:00:00",
			"items": [{"item": ITEM, "target_warehouse": WAREHOUSE, "quantity": 2.5, "rate": 12.5}],
		}
	)
	entry.insert()
	entry.submit()
	# Persist the disposable migration fixture across bench commands.
	frappe.db.commit()  # nosemgrep: frappe-manual-commit
	# Simulate the legacy Data columns and missing method audit fields.
	frappe.db.sql(
		"ALTER TABLE `tabStock Ledger Entry` MODIFY qty_after_transaction VARCHAR(140), MODIFY stock_value_after_transaction VARCHAR(140)"
	)
	for field in ("qty_after_transaction", "stock_value_after_transaction"):
		frappe.db.set_value(
			"DocField", {"parent": "Stock Ledger Entry", "fieldname": field}, "fieldtype", "Data"
		)
	frappe.db.set_value(
		"DocType",
		"Stock Ledger Entry",
		{"migration_hash": "legacy-smoke", "modified": "2026-01-01 00:00:00"},
		update_modified=False,
	)
	frappe.db.sql("UPDATE `tabStock Ledger Entry` SET valuation_method = NULL WHERE item = %s", ITEM)
	for patch in (
		"warehouse_management.patches.validate_ledger_numbers",
		"warehouse_management.patches.secure_ledger",
	):
		frappe.db.delete("Patch Log", {"patch": patch})
	# Persist the disposable migration fixture across bench commands.
	frappe.db.commit()  # nosemgrep: frappe-manual-commit


def verify():
	rows = frappe.db.sql(
		"SELECT qty_after_transaction, stock_value_after_transaction FROM `tabStock Ledger Entry` WHERE item = %s",
		ITEM,
	)
	assert len(rows) == 1
	assert float(rows[0][0]) == 2.5 and float(rows[0][1]) == 31.25
	columns = {
		row.Field: row.Type
		for row in frappe.db.sql("SHOW COLUMNS FROM `tabStock Ledger Entry`", as_dict=True)
	}
	assert columns["qty_after_transaction"].startswith("decimal")
	assert columns["stock_value_after_transaction"].startswith("decimal")
	for role in frappe.get_all(
		"DocPerm", filters={"parent": "Stock Ledger Entry"}, fields=["create", "write", "delete"]
	):
		assert not role.create and not role.write and not role.delete
	# First migration requires explicit audit; the second is idempotent.
	confirm_valuation(ITEM, "FIFO")
	assert frappe.db.get_value("Stock Ledger Entry", {"item": ITEM}, "valuation_method") == "FIFO"
