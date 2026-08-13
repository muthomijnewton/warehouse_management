# Copyright (c) 2026, Newton Muthomi and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	filters = filters or {}

	columns = get_columns()

	opening_qty, opening_value = get_opening_balance(filters)
	ledger_data = get_data(filters)

	data = [{
		"description": "Opening Balance",
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
	}]

	data.extend(ledger_data)

	closing_qty = opening_qty + sum(
		row.actual_quantity or 0 
		for row in ledger_data
	)

	closing_value = opening_value + sum(
		row.stock_value or 0
		for row in ledger_data
	)

	closing_rate = (
		closing_value / closing_qty
		if closing_qty > 0
		else 0
	)

	data.append({
		"description": "Closing Balance",
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
	})

	return columns, data

def get_columns():
	return[
		{
			"label": "Description",
			"fieldname": "description",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": "Posting Date",
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": "Posting Time",
			"fieldname": "posting_time",
			"fieldtype": "Time",
			"width": 100,
		},
		{
			"label": "Item",
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": "Warehouse",
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 120,
		},
		{
			"label": "Stock Entry",
			"fieldname": "stock_entry",
			"fieldtype":"Link",
			"options": "Stock Entry",
			"width": 120,
		},
		{
			"label": "Actual Quantity",
			"fieldname": "actual_quantity",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": "Valuation Rate",
			"fieldname": "valuation_rate",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": "Stock Value",
			"fieldname": "stock_value",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": "Qty After Transaction",
			"fieldname": "qty_after_transaction",
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"label": "Stock Value After Transaction",
			"fieldname": "stock_value_after_transaction",
			"fieldtype": "Currency",
			"width": 180,
		},
	]
def get_opening_balance(filters):
	conditions = [
		"posting_date < %(from_date)s"
	]

	values = {
		"from_date": filters.get("from_date")
	}

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
			COALESCE(SUM(actual_quantity), 0) AS quantity,
			COALESCE(SUM(stock_value), 0) AS value
		FROM `tabStock Ledger Entry`
		WHERE {where_clause}
		""",
		values,
		as_dict=True,
	)

	return result[0].quantity, result[0].value

def get_data(filters):
	conditions = []
	values = {}

	if filters.get("item"):
		conditions.append("item = %(item)s")
		values["item"] = filters["item"]

	if filters.get("warehouse"):
		conditions.append("warehouse = %(warehouse)s")
		values["warehouse"] = filters["warehouse"]

	if filters.get("from_date"):
		conditions.append("posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions.append("posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	where_clause = ""

	if conditions:
		where_clause = "WHERE " + " AND ".join(conditions)

	return frappe.db.sql(
		f"""
		SELECT
			posting_date,
			posting_time,
			item,
			warehouse,
			stock_entry,
			actual_quantity,
			valuation_rate,
			stock_value,
			qty_after_transaction,
			stock_value_after_transaction
		FROM `tabStock Ledger Entry`
		{where_clause}
		ORDER BY posting_date, posting_time, creation
		""",
		values,
		as_dict = True,
	)

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
