# Copyright (c) 2026, Newton Muthomi and contributors
# For license information, please see license.txt

import frappe
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
			"label": "Item",
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": "Warehouse",
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 150,
		},
		{"label": "Quantity", "fieldname": "quantity", "fieldtype": "Float", "width": 100},
		{
			"label": "Stock Value",
			"fieldname": "stock_value",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": "Valuation Rate",
			"fieldname": "valuation_rate",
			"fieldtype": "Currency",
			"width": 120,
		},
	]


def get_data(filters):
	conditions = ["posting_date <= %(as_of_date)s"]

	values = {"as_of_date": filters.get("as_of_date")}

	if filters.get("item"):
		conditions.append("item = %(item)s")
		values["item"] = filters["item"]

	if filters.get("warehouse"):
		conditions.append("warehouse = %(warehouse)s")
		values["warehouse"] = filters["warehouse"]

	where_clause = " AND ".join(conditions)

	result = frappe.db.sql(
		f"""
		SELECT
			item,
			warehouse,
			SUM(actual_quantity) AS quantity,
			SUM(stock_value) AS stock_value
		FROM `tabStock Ledger Entry`
		WHERE {where_clause}
		GROUP BY item, warehouse
		ORDER BY item, warehouse
		""",
		values,
		as_dict=True,
	)

	for row in result:
		if row.quantity:
			row.valuation_rate = row.stock_value / row.quantity
		else:
			row.valuation_rate = 0

	return result
