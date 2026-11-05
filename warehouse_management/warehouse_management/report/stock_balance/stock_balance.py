# Copyright (c) 2026, Newton Muthomi and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, today


def execute(filters=None):
	filters = dict(filters or {})
	filters["as_of_date"] = getdate(filters.get("as_of_date") or today())

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	return [
		{
			"label": _("Item"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 150,
		},
		{"label": _("Quantity"), "fieldname": "quantity", "fieldtype": "Float", "width": 100},
		{
			"label": _("Stock Value"),
			"fieldname": "stock_value",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Valuation Rate"),
			"fieldname": "valuation_rate",
			"fieldtype": "Currency",
			"width": 120,
		},
	]


def get_data(filters):
	values = {
		"as_of_date": getdate(filters.get("as_of_date") or today()),
		"item": filters.get("item") or None,
		"warehouse": filters.get("warehouse") or None,
	}
	result = frappe.db.sql(
		"""SELECT item, warehouse, SUM(actual_quantity) AS quantity, SUM(stock_value) AS stock_value
		FROM `tabStock Ledger Entry`
		WHERE posting_date <= %(as_of_date)s
			AND (%(item)s IS NULL OR item = %(item)s)
			AND (%(warehouse)s IS NULL OR warehouse = %(warehouse)s)
		GROUP BY item, warehouse ORDER BY item, warehouse""",
		values,
		as_dict=True,
	)
	for row in result:
		row.valuation_rate = row.stock_value / row.quantity if row.quantity else 0
	return result
