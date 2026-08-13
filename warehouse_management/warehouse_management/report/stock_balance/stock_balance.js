// Copyright (c) 2026, Newton Muthomi and contributors
// For license information, please see license.txt

frappe.query_reports["Stock Balance"] = {
	"filters": [
		{
			fieldname: "as_of_date",
			label: "As of Date",
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "item",
			label: 'Item',
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "warehouse",
			label: "Warehouse",
			fieldtype: "Link",
			options: "Warehouse",
		},
	],
};
