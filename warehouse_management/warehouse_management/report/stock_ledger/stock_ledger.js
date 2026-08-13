// Copyright (c) 2026, Newton Muthomi and contributors
// For license information, please see license.txt

frappe.query_reports["Stock Ledger"] = {
	filters: [
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			label: "To Date",
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "item",
			label: "Item",
			fieldtype: "Link",
			options: "Item",
			reqd: 1,
		},
		{
			fieldname: "warehouse",
			label: "Warehouse",
			fieldtype:"Link",
			options: "Warehouse",
			reqd: 1,
		},
	],
};
