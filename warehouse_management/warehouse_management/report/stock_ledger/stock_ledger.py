# Copyright (c) 2026, Newton Muthomi and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters=None):
	filters = dict(filters or {})
	if not filters.get("item") or not filters.get("warehouse"):
		frappe.throw(_("Select an Item and Warehouse for the Stock Ledger report."))
	if (
		filters.get("from_date")
		and filters.get("to_date")
		and getdate(filters["from_date"]) > getdate(filters["to_date"])
	):
		frappe.throw(_("From Date must not be after To Date."))

	columns = get_columns()

	opening_qty, opening_value = get_opening_balance(filters)
	ledger_data = get_data(filters)

	data = [
		{
			"description": _("Opening Balance"),
			"posting_date": None,
			"posting_time": None,
			"item": filters.get("item"),
			"warehouse": filters.get("warehouse"),
			"stock_entry": None,
			"actual_quantity": None,
			"valuation_rate": None,
			"stock_value": None,
			"qty_after_transaction": opening_qty,
			"stock_value_after_transaction": opening_value,
		}
	]

	data.extend(ledger_data)

	closing_qty = opening_qty + sum(row.actual_quantity or 0 for row in ledger_data)

	closing_value = opening_value + sum(row.stock_value or 0 for row in ledger_data)

	closing_rate = closing_value / closing_qty if closing_qty > 0 else 0

	data.append(
		{
			"description": _("Closing Balance"),
			"posting_date": None,
			"posting_time": None,
			"item": filters.get("item"),
			"warehouse": filters.get("warehouse"),
			"stock_entry": None,
			"actual_quantity": None,
			"valuation_rate": closing_rate,
			"stock_value": None,
			"qty_after_transaction": closing_qty,
			"stock_value_after_transaction": closing_value,
		}
	)

	return columns, data


def get_columns():
	return [
		{
			"label": _("Description"),
			"fieldname": "description",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("Posting Time"),
			"fieldname": "posting_time",
			"fieldtype": "Time",
			"width": 100,
		},
		{
			"label": _("Item"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 120,
		},
		{
			"label": _("Stock Entry"),
			"fieldname": "stock_entry",
			"fieldtype": "Link",
			"options": "Stock Entry",
			"width": 120,
		},
		{
			"label": _("Actual Quantity"),
			"fieldname": "actual_quantity",
			"fieldtype": "Float",
			"width": 120,
		},
		{"label": _("Valuation Rate"), "fieldname": "valuation_rate", "fieldtype": "Currency", "width": 120},
		{"label": _("Stock Value"), "fieldname": "stock_value", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Qty After Transaction"),
			"fieldname": "qty_after_transaction",
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"label": _("Stock Value After Transaction"),
			"fieldname": "stock_value_after_transaction",
			"fieldtype": "Currency",
			"width": 180,
		},
	]


def get_opening_balance(filters):
	if not filters.get("from_date"):
		return 0, 0
	result = frappe.db.sql(
		"""SELECT COALESCE(SUM(actual_quantity), 0) AS quantity,
			COALESCE(SUM(stock_value), 0) AS value
		FROM `tabStock Ledger Entry`
		WHERE posting_date < %(from_date)s AND item = %(item)s AND warehouse = %(warehouse)s""",
		filters,
		as_dict=True,
	)
	return result[0].quantity, result[0].value


def get_data(filters):
	values = {
		"item": filters.get("item"),
		"warehouse": filters.get("warehouse"),
		"from_date": filters.get("from_date") or None,
		"to_date": filters.get("to_date") or None,
	}
	return frappe.db.sql(
		"""SELECT posting_date, posting_time, item, warehouse, stock_entry, actual_quantity,
			valuation_rate, stock_value, qty_after_transaction, stock_value_after_transaction
		FROM `tabStock Ledger Entry`
		WHERE item = %(item)s AND warehouse = %(warehouse)s
			AND (%(from_date)s IS NULL OR posting_date >= %(from_date)s)
			AND (%(to_date)s IS NULL OR posting_date <= %(to_date)s)
		ORDER BY posting_date, posting_time, creation, name""",
		values,
		as_dict=True,
	)
