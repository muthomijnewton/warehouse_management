# Copyright (c) 2026, Newton Muthomi and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today


class TestStockEntry(FrappeTestCase):

	def setUp(self):
		self.item = self.get_item()

		item = frappe.get_doc("Item", self.item)
		item.valuation_method = None
		item.save(ignore_permissions=True)

		frappe.db.set_single_value(
			"Warehouse Settings",
			"default_valuation_method",
			"Moving Average",
		)

		self.shelf_a = self.get_warehouse(
			"Test Shelf A",
			"TEST-SHELF-A",
		)

		self.shelf_b = self.get_warehouse(
			"Test Shelf B",
			"TEST-SHELF-B",
		)

		frappe.db.delete(
			"Stock Ledger Entry",
			{
				"item": self.item,
				"warehouse": ["in", [self.shelf_a, self.shelf_b]],
			},
		)

		frappe.db.commit()

	def get_item(self):
		if frappe.db.exists("Item", "TEST-LAP001"):
			return "TEST-LAP001"

		item = frappe.get_doc({
			"doctype": "Item",
			"item_code": "TEST-LAP001",
			"item_name": "Test Laptop",
			"unit": "Piece",
			"standard_cost": 20000,
		})

		item.insert(ignore_permissions=True)

		return item.name

	def set_item_valuation_method(self, method):
			frappe.db.set_value(
					"Item",
					self.item,
					"valuation_method",
					method,
			)

	def set_global_valuation_method(self, method):
			frappe.db.set_single_value(
					"Warehouse Settings",
					"default_valuation_method",
					method,
			)

	def get_warehouse(self, name, code):
		if frappe.db.exists("Warehouse", name):
			return name

		warehouse = frappe.get_doc({
			"doctype": "Warehouse",
			"warehouse_name": name,
			"warehouse_code": code,
			"is_group": 0,
		})

		warehouse.insert(ignore_permissions=True)

		return warehouse.name

	def create_stock_entry(
		self,
		purpose,
		quantity,
		source_warehouse=None,
		target_warehouse=None,
		rate=20000,
	):
		return frappe.get_doc({
			"doctype": "Stock Entry",
			"posting_date": today(),
			"purpose": purpose,
			"items": [{
				"item": self.item,
				"quantity": quantity,
				"rate": rate,
				"source_warehouse": source_warehouse,
				"target_warehouse": target_warehouse,
			}],
		})

	def get_balance(self, warehouse):
		return self.get_stock_balance(
			self.item,
			warehouse,
		)

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

		return result[0]

	def test_receipt(self):
		entry = self.create_stock_entry(
			purpose="Receipt",
			quantity=50,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		entry.insert(ignore_permissions=True)
		entry.submit()

		qty, value = self.get_balance(self.shelf_a)

		self.assertEqual(qty, 50)
		self.assertEqual(value, 1_000_000)

	def test_insufficient_stock(self):
		entry = self.create_stock_entry(
			purpose="Consume",
			quantity=100,
			source_warehouse=self.shelf_a,
		)

		entry.insert(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			entry.submit()

	def test_same_warehouse_transfer(self):
		entry = self.create_stock_entry(
			purpose="Transfer",
			quantity=10,
			source_warehouse=self.shelf_a,
			target_warehouse=self.shelf_a,
		)

		with self.assertRaises(frappe.ValidationError):
			entry.insert(ignore_permissions=True)

	def test_transfer(self):
		# Create stock in Shelf A first.
		receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=50,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		receipt.insert(ignore_permissions=True)
		receipt.submit()

		# Transfer 20 units from Shelf A to Shelf B.
		transfer = self.create_stock_entry(
			purpose="Transfer",
			quantity=20,
			source_warehouse=self.shelf_a,
			target_warehouse=self.shelf_b,
		)

		transfer.insert(ignore_permissions=True)
		transfer.submit()

		source_qty, source_value = self.get_balance(self.shelf_a)
		target_qty, target_value = self.get_balance(self.shelf_b)

		self.assertEqual(source_qty, 30)
		self.assertEqual(source_value, 600_000)

		self.assertEqual(target_qty, 20)
		self.assertEqual(target_value, 400_000)

	def test_receipt_cancellation(self):
		entry = self.create_stock_entry(
			purpose="Receipt",
			quantity=30,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		entry.insert(ignore_permissions=True)
		entry.submit()

		qty_before_cancel, value_before_cancel = self.get_balance(
			self.shelf_a
		)

		self.assertEqual(qty_before_cancel, 30)
		self.assertEqual(value_before_cancel, 600_000)

		entry.cancel()

		qty_after_cancel, value_after_cancel = self.get_balance(
			self.shelf_a
		)

		self.assertEqual(qty_after_cancel, 0)
		self.assertEqual(value_after_cancel, 0)

	def test_consume_cancellation(self):
		receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=50,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		receipt.insert(ignore_permissions=True)
		receipt.submit()

		consume = self.create_stock_entry(
			purpose="Consume",
			quantity=20,
			source_warehouse=self.shelf_a,
		)

		consume.insert(ignore_permissions=True)
		consume.submit()

		qty_after_consume, value_after_consume = self.get_balance(
			self.shelf_a
		)

		self.assertEqual(qty_after_consume, 30)
		self.assertEqual(value_after_consume, 600_000)

		consume.cancel()

		qty_after_cancel, value_after_cancel = self.get_balance(
			self.shelf_a
		)

		self.assertEqual(qty_after_cancel, 50)
		self.assertEqual(value_after_cancel, 1_000_000)

	def test_transfer_cancellation(self):
		receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=50,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		receipt.insert(ignore_permissions=True)
		receipt.submit()

		transfer = self.create_stock_entry(
			purpose="Transfer",
			quantity=20,
			source_warehouse=self.shelf_a,
			target_warehouse=self.shelf_b,
		)

		transfer.insert(ignore_permissions=True)
		transfer.submit()

		transfer.cancel()

		source_qty, source_value = self.get_balance(self.shelf_a)
		target_qty, target_value = self.get_balance(self.shelf_b)

		self.assertEqual(source_qty, 50)
		self.assertEqual(source_value, 1_000_000)

		self.assertEqual(target_qty, 0)
		self.assertEqual(target_value, 0)

	def test_moving_average_valuation(self):
		first_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		first_receipt.insert(ignore_permissions=True)
		first_receipt.submit()

		second_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=30000,
		)

		second_receipt.insert(ignore_permissions=True)
		second_receipt.submit()

		qty, value = self.get_balance(self.shelf_a)

		self.assertEqual(qty, 20)
		self.assertEqual(value, 500_000)

		valuation_rate = value / qty

		self.assertEqual(valuation_rate, 25_000)

	def test_consume_uses_average_valuation(self):
		first_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		first_receipt.insert(ignore_permissions=True)
		first_receipt.submit()

		second_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=30000,
		)

		second_receipt.insert(ignore_permissions=True)
		second_receipt.submit()

		consume = self.create_stock_entry(
			purpose="Consume",
			quantity=4,
			source_warehouse=self.shelf_a,
		)

		consume.insert(ignore_permissions=True)
		consume.submit()

		qty, value = self.get_balance(self.shelf_a)

		self.assertEqual(qty, 16)
		self.assertEqual(value, 400_000)

	def test_fifo_valuation(self):
		self.set_item_valuation_method("FIFO")

		first_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		first_receipt.insert(ignore_permissions=True)
		first_receipt.submit()

		second_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=30000,
		)

		second_receipt.insert(ignore_permissions=True)
		second_receipt.submit()	

		consume = self.create_stock_entry(
			purpose="Consume",
			quantity=4,
			source_warehouse=self.shelf_a,
		)	

		consume.insert(ignore_permissions=True)
		consume.submit()

		qty, value = self.get_balance(self.shelf_a)

		self.assertEqual(qty, 16)
		self.assertEqual(value, 420_000)

	def test_fifo_transfer(self):

		self.set_item_valuation_method("FIFO")

		first_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		first_receipt.insert(ignore_permissions=True)
		first_receipt.submit()

		second_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=30000,
		)

		second_receipt.insert(ignore_permissions=True)
		second_receipt.submit()

		transfer = self.create_stock_entry(
			purpose="Transfer",
			quantity=12,
			source_warehouse=self.shelf_a,
			target_warehouse=self.shelf_b,
		)

		self.set_item_valuation_method("FIFO")
		transfer.insert(ignore_permissions=True)
		transfer.submit()

		source_qty, source_value = self.get_balance(
			self.shelf_a
		)

		target_qty, target_value = self.get_balance(
			self.shelf_b
		)

		self.assertEqual(source_qty, 8)
		self.assertEqual(source_value, 240000)

		self.assertEqual(target_qty, 12)
		self.assertEqual(target_value, 260000)

	def test_fifo_transfer_to_stocked_warehouse(self):
		# Create the first FIFO layer in Shelf A.
		first_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		self.set_item_valuation_method("FIFO")
		first_receipt.insert(ignore_permissions=True)
		first_receipt.submit()

		# Create the second FIFO layer in Shelf A.
		second_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=30000,
		)

		self.set_item_valuation_method("FIFO")
		second_receipt.insert(ignore_permissions=True)
		second_receipt.submit()

		# Put existing stock in Shelf B at a different rate.
		target_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=5,
			target_warehouse=self.shelf_b,
			rate=10000,
		)

		self.set_item_valuation_method("FIFO")
		target_receipt.insert(ignore_permissions=True)
		target_receipt.submit()

		# Transfer 12 units from Shelf A to Shelf B.
		transfer = self.create_stock_entry(
			purpose="Transfer",
			quantity=12,
			source_warehouse=self.shelf_a,
			target_warehouse=self.shelf_b,
		)

		self.set_item_valuation_method("FIFO")
		transfer.insert(ignore_permissions=True)
		transfer.submit()

		source_qty, source_value = self.get_balance(
			self.shelf_a
		)

		target_qty, target_value = self.get_balance(
			self.shelf_b
		)

		self.assertEqual(source_qty, 8)
		self.assertEqual(source_value, 240000)

		self.assertEqual(target_qty, 17)

		self.assertEqual(target_value, 310000)

	def test_fifo_consume_creates_stock_entry_allocations(self):
		self.set_item_valuation_method("FIFO")

		receipt_a = self.create_stock_entry(
			purpose="Receipt",
			target_warehouse=self.shelf_a,
			quantity=10,
			rate=20000,
		)
		receipt_a.submit()

		receipt_b = self.create_stock_entry(
			purpose="Receipt",
			target_warehouse=self.shelf_a,
			quantity=15,
			rate=22000,
		)
		receipt_b.submit()

		consume = self.create_stock_entry(
			purpose="Consume",
			source_warehouse=self.shelf_a,
			quantity=12,
		)
		consume.submit()

		self.assertEqual(len(consume.stock_entry_allocations), 2)

		allocation_a = consume.stock_entry_allocations[0]
		allocation_b = consume.stock_entry_allocations[1]

		self.assertEqual(allocation_a.item, self.item)
		self.assertEqual(allocation_a.stock_entry, receipt_a.name)
		self.assertEqual(allocation_a.quantity, 10)
		self.assertEqual(allocation_a.valuation_rate, 20000)
		self.assertEqual(allocation_a.value, 200000)

		self.assertEqual(allocation_b.item, self.item)
		self.assertEqual(allocation_b.stock_entry, receipt_b.name)
		self.assertEqual(allocation_b.quantity, 2)
		self.assertEqual(allocation_b.valuation_rate, 22000)
		self.assertEqual(allocation_b.value, 44000)

	def test_lifo_receipt(self):
		first_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		self.set_item_valuation_method("LIFO")
		first_receipt.insert(ignore_permissions=True)
		first_receipt.submit()

		second_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=30000,
		)

		self.set_item_valuation_method("LIFO")
		second_receipt.insert(ignore_permissions=True)
		second_receipt.submit()

		qty, value = self.get_balance(self.shelf_a)

		self.assertEqual(qty, 20)
		self.assertEqual(value, 500000)

	def test_lifo_valuation(self):
		first_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		self.set_item_valuation_method("LIFO")
		first_receipt.insert(ignore_permissions=True)
		first_receipt.submit()

		second_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=30000,
		)

		self.set_item_valuation_method("LIFO")
		second_receipt.insert(ignore_permissions=True)
		second_receipt.submit()

		consume = self.create_stock_entry(
			purpose="Consume",
			quantity=4,
			source_warehouse=self.shelf_a,
		)

		self.set_item_valuation_method("LIFO")
		consume.insert(ignore_permissions=True)
		consume.submit()

		qty, value = self.get_balance(self.shelf_a)

		self.assertEqual(qty, 16)
		self.assertEqual(value, 380000)

	def test_lifo_transfer(self):
		# Shelf A: first LIFO layer
		first_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		self.set_item_valuation_method("LIFO")
		first_receipt.insert(ignore_permissions=True)
		first_receipt.submit()

		# Shelf A: second LIFO layer
		second_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=30000,
		)

		self.set_item_valuation_method("LIFO")
		second_receipt.insert(ignore_permissions=True)
		second_receipt.submit()

		# Transfer 12 units from Shelf A to Shelf B using LIFO.
		transfer = self.create_stock_entry(
			purpose="Transfer",
			quantity=12,
			source_warehouse=self.shelf_a,
			target_warehouse=self.shelf_b,
		)

		self.set_item_valuation_method("LIFO")
		transfer.insert(ignore_permissions=True)
		transfer.submit()

		source_qty, source_value = self.get_balance(
			self.shelf_a
		)

		target_qty, target_value = self.get_balance(
			self.shelf_b
		)

		# LIFO transfer:
		#
		# 10 × 30,000 = 300,000
		#  2 × 20,000 =  40,000
		# Total transferred = 340,000
		#
		# Shelf A is left with:
		# 8 × 20,000 = 160,000

		self.assertEqual(source_qty, 8)
		self.assertEqual(source_value, 160000)

		self.assertEqual(target_qty, 12)
		self.assertEqual(target_value, 340000)

	def test_fifo_layers_preserve_stock_entry(self):
		first_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		self.set_item_valuation_method("FIFO")
		first_receipt.insert(ignore_permissions=True)
		first_receipt.submit()

		second_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=20,
			target_warehouse=self.shelf_a,
			rate=25000,
		)

		self.set_item_valuation_method("FIFO")
		second_receipt.insert(ignore_permissions=True)
		second_receipt.submit()

		layers = second_receipt.get_fifo_layers(
			self.item,
			self.shelf_a,
		)

		test_layers = [
			layer
			for layer in layers
			if layer["stock_entry"] in {
				first_receipt.name,
				second_receipt.name,
			}
		]

		self.assertEqual(len(test_layers), 2)

		self.assertEqual(
			test_layers[0]["stock_entry"],
			first_receipt.name,
		)
		self.assertEqual(test_layers[0]["quantity"], 10)
		self.assertEqual(test_layers[0]["rate"], 20000)

		self.assertEqual(
			test_layers[1]["stock_entry"],
			second_receipt.name,
		)
		self.assertEqual(test_layers[1]["quantity"], 20)
		self.assertEqual(test_layers[1]["rate"], 25000)
			
	def test_fifo_consumption_tracks_stock_entry_layers(self):
		first_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=20000,
		)

		self.set_item_valuation_method("FIFO")
		first_receipt.insert(ignore_permissions=True)
		first_receipt.submit()

		second_receipt = self.create_stock_entry(
			purpose="Receipt",
			quantity=10,
			target_warehouse=self.shelf_a,
			rate=30000,
		)

		self.set_item_valuation_method("FIFO")
		second_receipt.insert(ignore_permissions=True)
		second_receipt.submit()

		consume = self.create_stock_entry(
			purpose="Consume",
			quantity=12,
			source_warehouse=self.shelf_a,
			rate=0,
		)

		self.set_item_valuation_method("FIFO")
		consume.insert(ignore_permissions=True)

		valuation = consume.calculate_consume_fifo_valuation(
			consume.items[0]
		)

		consumed_layers = valuation["consumed_layers"]

		self.assertEqual(len(consumed_layers), 2)

		self.assertEqual(
			consumed_layers[0]["stock_entry"],
			first_receipt.name,
		)
		self.assertEqual(
			consumed_layers[0]["quantity"],
			10,
		)
		self.assertEqual(
			consumed_layers[0]["rate"],
			20000,
		)

		self.assertEqual(
			consumed_layers[1]["stock_entry"],
			second_receipt.name,
		)
		self.assertEqual(
			consumed_layers[1]["quantity"],
			2,
		)
		self.assertEqual(
			consumed_layers[1]["rate"],
			30000,
		)

		self.assertEqual(
			valuation["movement_value"],
			-260000,
		)

	def test_global_fifo_when_item_method_is_blank(self):
			self.set_global_valuation_method("FIFO")
			self.set_item_valuation_method(None)

			stock_entry = self.create_stock_entry(
					purpose="Receipt",
					quantity=1,
					target_warehouse=self.shelf_a,
			)

			self.assertEqual(
					stock_entry.get_valuation_method(self.item),
					"FIFO",
			)


	def test_global_lifo_when_item_method_is_blank(self):
			self.set_global_valuation_method("LIFO")
			self.set_item_valuation_method(None)

			stock_entry = self.create_stock_entry(
					purpose="Receipt",
					quantity=1,
					target_warehouse=self.shelf_a,
			)

			self.assertEqual(
					stock_entry.get_valuation_method(self.item),
					"LIFO",
			)


	def test_item_lifo_overrides_global_fifo(self):
			self.set_global_valuation_method("FIFO")
			self.set_item_valuation_method("LIFO")

			stock_entry = self.create_stock_entry(
					purpose="Receipt",
					quantity=1,
					target_warehouse=self.shelf_a,
			)

			self.assertEqual(
					stock_entry.get_valuation_method(self.item),
					"LIFO",
			)


	def test_item_fifo_overrides_global_lifo(self):
			self.set_global_valuation_method("LIFO")
			self.set_item_valuation_method("FIFO")

			stock_entry = self.create_stock_entry(
					purpose="Receipt",
					quantity=1,
					target_warehouse=self.shelf_a,
			)

			self.assertEqual(
					stock_entry.get_valuation_method(self.item),
					"FIFO",
			)