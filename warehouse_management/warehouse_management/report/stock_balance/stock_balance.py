# Copyright (c) 2026, Newton Muthomi and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data

def get_columns():
	return[
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
		{
			"label": "Quantity",
			"fieldname": "quantity",
			"fieldtype": "Float",
			"width": 100
		},
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
	conditions = [
		"posting_date <= %(as_of_date)s"
	]

	values = {
		"as_of_date": filters.get("as_of_date")
	}

	if filters.get("item"):
		conditions.append("item = %(item)s")
		values["item"] = filters["item"]

	if filters.get("warehouse"):
		conditions.append("item = %(item)s")
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
			row.valuation_rate = row.stock_value/row.quantity
		else:
			row.valuation_rate = 0

	return result

def execute_snapshot_report(filters: dict | None = None):
	"""Return columns and data for the report.

	This is the main entry point for snapshot report. When 'Synced
	Report' is enabled in report, framework will call this method
	every time the report is refreshed or a filter is updated. It
	accepts the same filters as normal execute. But a utility method -
	get_latest_sync, is also imported.

	"""
	from frappe.database.duckdb.database import get_latest_sync

	columns, data = [], []
	return columns, data
