# Copyright (c) 2026, Newton Muthomi and contributors
# For license information, please see license.txt

import math

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, now_datetime

from warehouse_management.warehouse_management.doctype.stock_ledger_entry.stock_ledger_entry import (
	LEDGER_WRITE_TOKEN,
)

METHODS = ("Moving Average", "FIFO", "LIFO")


class StockEntry(Document):
	def validate(self):
		self.validate_rows()
		self.validate_warehouses()
		self.validate_items()

	def validate_rows(self):
		if self.purpose not in ("Receipt", "Consume", "Transfer"):
			frappe.throw(_("Purpose must be Receipt, Consume, or Transfer."))
		if not self.items:
			frappe.throw(_("Add at least one item."))
		for row in self.items:
			if not math.isfinite(flt(row.quantity)) or flt(row.quantity) <= 0:
				frappe.throw(_("Row {0}: Quantity must be greater than zero and finite.").format(row.idx))
			if not math.isfinite(flt(row.rate)) or flt(row.rate) < 0:
				frappe.throw(_("Row {0}: Rate must be non-negative and finite.").format(row.idx))
			if self.purpose in ("Consume", "Transfer") and not row.source_warehouse:
				frappe.throw(
					_("Row {0}: Source Warehouse is required for {1}.").format(row.idx, self.purpose)
				)
			if self.purpose in ("Receipt", "Transfer") and not row.target_warehouse:
				frappe.throw(
					_("Row {0}: Target Warehouse is required for {1}.").format(row.idx, self.purpose)
				)
			if self.purpose == "Receipt" and row.source_warehouse:
				frappe.throw(_("Row {0}: Source Warehouse should be empty for Receipt.").format(row.idx))
			if self.purpose == "Consume" and row.target_warehouse:
				frappe.throw(_("Row {0}: Target Warehouse should be empty for Consume.").format(row.idx))
			if self.purpose == "Transfer" and row.source_warehouse == row.target_warehouse:
				frappe.throw(_("Row {0}: Source and Target Warehouse cannot be the same.").format(row.idx))

	def validate_warehouses(self):
		for row in self.items:
			for name in {row.source_warehouse, row.target_warehouse} - {None, ""}:
				warehouse = frappe.get_cached_doc("Warehouse", name)
				if warehouse.is_group:
					frappe.throw(_("{0} is a group warehouse. Please select a child warehouse.").format(name))
				if warehouse.disabled:
					frappe.throw(_("Warehouse {0} is disabled.").format(name))

	def validate_items(self):
		for row in self.items:
			if frappe.get_cached_doc("Item", row.item).disabled:
				frappe.throw(_("Item {0} is disabled.").format(row.item))

	def get_valuation_method(self, item):
		method = frappe.db.get_value("Item", item, "valuation_method") or frappe.db.get_single_value(
			"Warehouse Settings", "default_valuation_method"
		)
		if method not in METHODS:
			frappe.throw(_("Set a supported valuation method on the Item or in Warehouse Settings."))
		return method

	def lock_items(self):
		# Existing Item rows also protect empty warehouses. Hold locks until commit/rollback.
		# Sorting prevents opposite-direction transfers acquiring locks in opposite orders.
		for item in sorted({row.item for row in self.items}):
			frappe.db.sql("SELECT name FROM `tabItem` WHERE name = %s FOR UPDATE", item)

	def get_item_history(self, item):
		# A locking read sees the latest committed rows after waiting for the Item lock,
		# even when the transaction already has a repeatable-read snapshot.
		return frappe.db.sql(
			"""SELECT name, stock_entry, item, warehouse, actual_quantity, stock_value,
				valuation_rate, valuation_method, posting_date, posting_time, creation, reversal_of
			FROM `tabStock Ledger Entry` WHERE item = %s
			ORDER BY posting_date, posting_time, creation, name FOR UPDATE""",
			item,
			as_dict=True,
		)

	def validate_chronology(self, timestamp):
		if timestamp > now_datetime():
			frappe.throw(_("Future stock postings are not allowed."))
		for item in sorted({row.item for row in self.items}):
			history = self.get_item_history(item)
			if history and timestamp < get_datetime(f"{history[-1].posting_date} {history[-1].posting_time}"):
				frappe.throw(
					_(
						"Backdated stock postings are not allowed for item {0}. Use the latest posting time or later."
					).format(item)
				)

	def before_submit(self):
		self.lock_items()
		self.validate_chronology(get_datetime(f"{self.posting_date} {self.posting_time}"))
		methods = set()
		for row in self.items:
			method = self.get_valuation_method(row.item)
			history = self.get_item_history(row.item)
			if any(not entry.valuation_method for entry in history):
				frappe.throw(
					_(
						"Legacy stock history for item {0} needs a valuation audit. See the upgrade guide."
					).format(row.item)
				)
			if any(entry.valuation_method != method for entry in history):
				frappe.throw(
					_("Cannot change valuation method for item {0} with stock history.").format(row.item)
				)
			row.valuation_method_used = method
			methods.add(method)
		self.valuation_method_used = next(iter(methods)) if len(methods) == 1 else "Mixed (see items)"
		# Never accept client-supplied layer allocations.
		self.set("stock_entry_allocations", [])

	def on_submit(self):
		{"Receipt": self.handle_receipt, "Consume": self.handle_consume, "Transfer": self.handle_transfer}[
			self.purpose
		]()
		self.update_child_table("stock_entry_allocations")

	def row_method(self, row):
		return row.valuation_method_used or self.get_valuation_method(row.item)

	def handle_receipt(self):
		for row in self.items:
			valuation = self.calculate_receipt_valuation(row)
			self.post_movement(
				row,
				row.target_warehouse,
				row.quantity,
				valuation["movement_value"],
				valuation["valuation_rate"],
			)

	def handle_consume(self):
		for row in self.items:
			method = self.row_method(row)
			valuation = self.consume_valuation(row, method)
			if method != "Moving Average":
				self.create_stock_entry_allocations(row.item, valuation["consumed_layers"])
			self.post_movement(
				row,
				row.source_warehouse,
				-row.quantity,
				valuation["movement_value"],
				valuation["valuation_rate"],
			)

	def handle_transfer(self):
		for row in self.items:
			method = self.row_method(row)
			valuation = self.consume_valuation(row, method)
			if method == "Moving Average":
				layers = [
					{
						"quantity": row.quantity,
						"rate": valuation["valuation_rate"],
						"value": -valuation["movement_value"],
					}
				]
			else:
				layers = valuation["consumed_layers"]
				self.create_stock_entry_allocations(row.item, layers)
			for layer in layers:
				self.post_movement(
					row, row.source_warehouse, -layer["quantity"], -layer["value"], layer["rate"]
				)
				self.post_movement(
					row, row.target_warehouse, layer["quantity"], layer["value"], layer["rate"]
				)

	def post_movement(self, row, warehouse, qty, value, rate, reversal_of=None, timestamp=None):
		balance_qty, balance_value = self.get_stock_balance(row.item, warehouse)
		new_qty, new_value = flt(balance_qty + flt(qty), 9), balance_value + flt(value)
		if new_qty < 0:
			frappe.throw(_("Not enough stock for item {0} in warehouse {1}.").format(row.item, warehouse))
		self.create_ledger_entry(
			row.item,
			warehouse,
			qty,
			rate,
			value,
			new_qty,
			new_value,
			valuation_method=self.row_method(row),
			reversal_of=reversal_of,
			timestamp=timestamp,
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
		valuation_method=None,
		reversal_of=None,
		timestamp=None,
	):
		ledger = frappe.new_doc("Stock Ledger Entry")
		ledger.posting_date = timestamp.date() if timestamp else self.posting_date
		ledger.posting_time = timestamp.time() if timestamp else self.posting_time
		ledger.item = item
		ledger.warehouse = warehouse
		ledger.stock_entry = self.name
		ledger.actual_quantity = qty
		ledger.valuation_rate = valuation_rate
		ledger.stock_value = movement_value
		ledger.qty_after_transaction = qty_after_transaction
		ledger.stock_value_after_transaction = stock_value_after_transaction
		ledger.valuation_method = valuation_method or self.get_valuation_method(item)
		ledger.reversal_of = reversal_of
		ledger.flags.stock_write_token = LEDGER_WRITE_TOKEN
		ledger.insert(ignore_permissions=True)

	def create_stock_entry_allocations(self, item, layers):
		for layer in layers:
			self.append(
				"stock_entry_allocations",
				{
					"item": item,
					"stock_entry": layer["stock_entry"],
					"quantity": layer["quantity"],
					"valuation_rate": layer["rate"],
					"value": layer["value"],
				},
			)

	def get_stock_balance(self, item, warehouse):
		entries = [entry for entry in self.get_item_history(item) if entry.warehouse == warehouse]
		return sum(flt(e.actual_quantity) for e in entries), sum(flt(e.stock_value) for e in entries)

	def get_valuation_rate(self, item, warehouse):
		qty, value = self.get_stock_balance(item, warehouse)
		return value / qty if qty > 0 else 0

	def get_fifo_layers(self, item, warehouse):
		return self.get_stock_layers(item, warehouse)

	def get_lifo_layers(self, item, warehouse):
		return self.get_stock_layers(item, warehouse, lifo=True)

	def get_stock_layers(self, item, warehouse, lifo=False):
		history = self.get_item_history(item)
		reversed_names = {entry.reversal_of for entry in history if entry.reversal_of}
		layers = []
		for entry in history:
			if entry.warehouse != warehouse or entry.reversal_of or entry.name in reversed_names:
				continue
			qty = flt(entry.actual_quantity)
			if qty > 0:
				layers.append(
					{"stock_entry": entry.stock_entry, "quantity": qty, "rate": flt(entry.stock_value) / qty}
				)
			else:
				remaining = -qty
				while flt(remaining, 9) > 0 and layers:
					layer = layers[-1] if lifo else layers[0]
					take = min(layer["quantity"], remaining)
					layer["quantity"] -= take
					remaining -= take
					if flt(layer["quantity"], 9) <= 0:
						layers.pop(-1 if lifo else 0)
				if flt(remaining, 9) > 0:
					frappe.throw(
						_("Stock ledger is inconsistent for item {0} in warehouse {1}.").format(
							item, warehouse
						)
					)
		return layers

	def calculate_receipt_valuation(self, row):
		qty, value = self.get_stock_balance(row.item, row.target_warehouse)
		movement = flt(row.quantity) * flt(row.rate)
		new_qty, new_value = qty + row.quantity, value + movement
		rate = flt(row.rate) if self.row_method(row) != "Moving Average" else new_value / new_qty
		return {
			"qty_after_transaction": new_qty,
			"stock_value_after_transaction": new_value,
			"valuation_rate": rate,
			"movement_value": movement,
		}

	def consume_valuation(self, row, method):
		qty, value = self.get_stock_balance(row.item, row.source_warehouse)
		if flt(qty - row.quantity, 9) < 0:
			frappe.throw(
				_("Not enough stock for item {0} in warehouse {1}.").format(row.item, row.source_warehouse)
			)
		consumed = []
		if method == "Moving Average":
			issued = row.quantity * (value / qty)
		else:
			layers = self.get_stock_layers(row.item, row.source_warehouse, lifo=method == "LIFO")
			remaining = row.quantity
			for layer in reversed(layers) if method == "LIFO" else layers:
				take = min(layer["quantity"], remaining)
				if take > 0:
					consumed.append({**layer, "quantity": take, "value": take * layer["rate"]})
					remaining -= take
				if flt(remaining, 9) <= 0:
					break
			if flt(remaining, 9) > 0:
				frappe.throw(_("Stock ledger is inconsistent for item {0}.").format(row.item))
			issued = sum(layer["value"] for layer in consumed)
		return {
			"valuation_rate": issued / row.quantity,
			"movement_value": -issued,
			"qty_after_transaction": qty - row.quantity,
			"stock_value_after_transaction": value - issued,
			"consumed_layers": consumed,
		}

	def calculate_consume_valuation(self, row):
		return self.consume_valuation(row, "Moving Average")

	def calculate_consume_fifo_valuation(self, row):
		return self.consume_valuation(row, "FIFO")

	def calculate_consume_lifo_valuation(self, row):
		return self.consume_valuation(row, "LIFO")

	def calculate_transfer_fifo_valuation(self, row):
		valuation = self.consume_valuation(row, "FIFO")
		return {"layers": valuation["consumed_layers"], "total_value": -valuation["movement_value"]}

	def calculate_transfer_lifo_valuation(self, row):
		valuation = self.consume_valuation(row, "LIFO")
		return {"layers": valuation["consumed_layers"], "total_value": -valuation["movement_value"]}

	def before_cancel(self):
		self.lock_items()
		self.flags.ignore_links = True  # Ledger links remain as permanent audit records.
		for item in {row.item for row in self.items}:
			history = self.get_item_history(item)
			reversed_names = {e.reversal_of for e in history if e.reversal_of}
			active = [e for e in history if not e.reversal_of and e.name not in reversed_names]
			if not active or active[-1].stock_entry != self.name:
				frappe.throw(_("Cancel later stock entries for item {0} first.").format(item))
			if any(not e.valuation_method for e in history):
				frappe.throw(
					_(
						"Legacy stock history for item {0} needs a valuation audit. See the upgrade guide."
					).format(item)
				)
		self.validate_chronology(now_datetime())

	def on_cancel(self):
		# Reverse in reverse insertion order, preserving every original quantity and value.
		entries = frappe.db.sql(
			"""SELECT name, item, warehouse, actual_quantity, stock_value, valuation_rate, valuation_method
			FROM `tabStock Ledger Entry` WHERE stock_entry = %s AND COALESCE(reversal_of, '') = ''
			ORDER BY creation DESC, name DESC FOR UPDATE""",
			self.name,
			as_dict=True,
		)
		if not entries:
			frappe.throw(_("Cannot cancel a stock entry without original ledger entries."))
		timestamp = now_datetime()
		for entry in entries:
			row = frappe._dict(item=entry.item, valuation_method_used=entry.valuation_method)
			self.post_movement(
				row,
				entry.warehouse,
				-flt(entry.actual_quantity),
				-flt(entry.stock_value),
				entry.valuation_rate,
				reversal_of=entry.name,
				timestamp=timestamp,
			)

	def on_trash(self):
		if frappe.db.exists("Stock Ledger Entry", {"stock_entry": self.name}):
			frappe.throw(_("Stock entries with ledger history cannot be deleted."))

	def before_rename(self, old_name, new_name, merge=False):
		if frappe.db.exists("Stock Ledger Entry", {"stock_entry": old_name}):
			frappe.throw(_("Stock entries with ledger history cannot be renamed."))
