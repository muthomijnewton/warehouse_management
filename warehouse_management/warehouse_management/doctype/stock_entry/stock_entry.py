# Copyright (c) 2026, Newton Muthomi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StockEntry(Document):
	def validate(self):
		self.validate_rows()
		self.validate_warehouses()
		self.validate_items()

	def validate_rows(self):
		for row in self.items:
			if row.quantity <= 0:
				frappe.throw(
					f'Row {row.idx}: Quantity must be greater than zero'
				)

			if self.purpose == "Receipt":
				if not row.target_warehouse:
					frappe.throw(
						f"Row {row.idx}: Target Warehouse is required for Receipt."
					)

				if row.source_warehouse:
					frappe.throw(
						f"Row {row.idx}: Source Warehouse should be empty for Receipt."
					)

			elif self.purpose == "Consume":
				if not row.source_warehouse:
					frappe.throw(
						f"Row {row.idx}: Source Warehouse is required for Consume."
					)

				if row.target_warehouse:
					frappe.throw(
						f"Row {row.idx}: Target Warehouse should be empty for Consume."
					)

			elif self.purpose == "Transfer":
				if not row.source_warehouse:
					frappe.throw(
						f"Row {row.idx}: Source Warehouse is required for Transfer."
					)

				if not row.target_warehouse:
					frappe.throw(
						f"Row {row.idx}: Target Warehouse is required for Transfer."
					)

				if row.source_warehouse == row.target_warehouse:
					frappe.throw(
						f"Row {row.idx}: Source and Target Warehouse cannot be the same."
					)

	def validate_warehouses(self):
		for row in self.items:
			warehouses = []

			if row.source_warehouse:
				warehouses.append(row.source_warehouse)

			if row.target_warehouse:
				warehouses.append(row.target_warehouse)

			for warehouse_name in warehouses:
				warehouse = frappe.get_cached_doc(
					"Warehouse",
					warehouse_name
				)

				if warehouse.is_group:
					frappe.throw(
						f"{warehouse.name} is a group warehouse. "
						"Please select a child warehouse."
					)

				if warehouse.disabled:
					frappe.throw(
						f"Warehouse {warehouse.name} is disabled."
					) 

	def validate_items(self):
		for row in self.items:
			item = frappe.get_cached_doc(
				"Item",
				row.item
			)

			if item.disabled:
				frappe.throw(
					f"Item {item.name} is disabled."
				)

	def on_submit(self):
		if self.purpose == 'Receipt':
			self.handle_receipt()

		elif self.purpose == 'Consume':
			self.handle_consume()

		elif self.purpose == 'Transfer':
			self.handle_transfer()

	def handle_receipt(self):
		for row in self.items:
			valuation = self.calculate_receipt_valuation(row)

			self.create_ledger_entry(
				item=row.item,
				warehouse=row.target_warehouse,
				qty=row.quantity,
				valuation_rate=valuation["valuation_rate"],
				movement_value=valuation["movement_value"],
				qty_after_transaction=valuation["qty_after_transaction"],
				stock_value_after_transaction=valuation["stock_value_after_transaction"],
			)

	def handle_consume(self):
		for row in self.items:
			valuation = self.calculate_consume_valuation(row)

			self.create_ledger_entry(
				item=row.item,
				warehouse=row.source_warehouse,
				qty=-row.quantity,
				valuation_rate=valuation["valuation_rate"],
				movement_value=valuation["movement_value"],
				qty_after_transaction=valuation["qty_after_transaction"],
				stock_value_after_transaction=valuation["stock_value_after_transaction"],
			)

	def handle_transfer(self):
		for row in self.items:
			source, target = self.calculate_transfer_valuation(row)

			self.create_ledger_entry(
				item=row.item,
				warehouse=row.source_warehouse,
				qty=-row.quantity,
				valuation_rate=source["valuation_rate"],
				movement_value=source["movement_value"],
				qty_after_transaction=source["qty_after_transaction"],
				stock_value_after_transaction=source["stock_value_after_transaction"],
			)

			self.create_ledger_entry(
				item=row.item,
				warehouse=row.target_warehouse,
				qty=row.quantity,
				valuation_rate=target["valuation_rate"],
				movement_value=target["movement_value"],
				qty_after_transaction=target["qty_after_transaction"],
				stock_value_after_transaction=target["stock_value_after_transaction"],
			)

	def create_ledger_entry(
			self,
			item,
			warehouse,
			qty,
			valuation_rate,
			movement_value,
			qty_after_transaction,
			stock_value_after_transaction,
	):
		ledger = frappe.new_doc("Stock Ledger Entry")

		ledger.posting_date = self.posting_date
		ledger.posting_time = self.posting_time
		ledger.item = item
		ledger.warehouse = warehouse
		ledger.stock_entry = self.name

		ledger.actual_quantity = qty
		ledger.valuation_rate = valuation_rate
		ledger.stock_value = movement_value

		ledger.qty_after_transaction = qty_after_transaction
		ledger.stock_value_after_transaction = stock_value_after_transaction

		ledger.insert(ignore_permissions=True)

	def get_stock_balance(self, item, warehouse):
		result = frappe.db.sql(
			"""
			SELECT
				COALESCE(SUM(actual_quantity), 0),
				COALESCE(SUM(stock_value), 0)
			FROM `tabStock Ledger Entry`
			WHERE item = %s
				AND warehouse = %s
			""",
			(item, warehouse),
		)

		quantity, value = result[0]

		return quantity, value

	def get_valuation_rate(self, item, warehouse):
		quantity, value = self.get_stock_balance(item, warehouse)

		if quantity <= 0:
			return 0

		return value/quantity

	def calculate_receipt_valuation(self, row):
		current_qty, current_value = self.get_stock_balance(
			row.item,
			row.target_warehouse,
		)

		new_qty = current_qty + row.quantity

		new_value = current_value + (row.quantity*row.rate)

		if new_qty:
			new_rate = new_value/new_qty
		else:
			new_rate = 0

		return{
			"qty_after_transaction": new_qty,
			"stock_value_after_transaction": new_value,
			"valuation_rate": new_rate,
			"movement_value": row.quantity*row.rate,
		}

	def calculate_consume_valuation(self, row):
		current_qty, current_value = self.get_stock_balance(
			row.item,
			row.source_warehouse,
		)

		if current_qty < row.quantity:
			frappe.throw(
				f"Not enought stock for item {row.item} in warehouse {row.source_warehouse}"
			)

		valuation_rate = self.get_valuation_rate(
			row.item,
			row.source_warehouse,
		)

		new_qty = current_qty - row.quantity

		issued_value = row.quantity*valuation_rate

		new_value = current_value - issued_value

		return {
			"valuation_rate": valuation_rate,
			"movement_value": -issued_value,
			"qty_after_transaction": new_qty,
			"stock_value_after_transaction": new_value,
		}

	def calculate_transfer_valuation(self, row):
		source = self.calculate_consume_valuation(row)

		target_qty, target_value = self.get_stock_balance(
			row.item,
			row.target_warehouse,
		)

		received_value = row.quantity*source["valuation_rate"]

		new_qty = target_qty + row.quantity
		new_value = target_value + received_value

		if new_qty:
			new_rate = new_value/new_qty
		else:
			new_rate = 0

		target = {
			"valuation_rate": new_rate,
			"movement_value": received_value,
			"qty_after_transaction": new_qty,
			"stock_value_after_transaction": new_value,
		}

		return source, target

