# Copyright (c) 2026, Newton Muthomi and contributors
# For license information, please see license.txt

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowtime, today

from warehouse_management.warehouse_management.doctype.stock_entry import test_stock_entry
from warehouse_management.warehouse_management.report.stock_balance import stock_balance
from warehouse_management.warehouse_management.report.stock_ledger import stock_ledger


class TestInventorySafety(FrappeTestCase):
	setUp = test_stock_entry.TestStockEntry.setUp
	get_item = test_stock_entry.TestStockEntry.get_item
	get_warehouse = test_stock_entry.TestStockEntry.get_warehouse
	get_stock_balance = test_stock_entry.TestStockEntry.get_stock_balance
	get_balance = test_stock_entry.TestStockEntry.get_balance
	create_stock_entry = test_stock_entry.TestStockEntry.create_stock_entry
	set_item_valuation_method = test_stock_entry.TestStockEntry.set_item_valuation_method

	def submit_entry(self, purpose, quantity, rate=0, target=None):
		entry = self.create_stock_entry(
			purpose,
			quantity,
			rate=rate,
			source_warehouse=self.shelf_a if purpose != "Receipt" else None,
			target_warehouse=target or (self.shelf_a if purpose == "Receipt" else None),
		)
		entry.insert(ignore_permissions=True)
		entry.submit()
		return entry

	def clear_ledger(self):
		frappe.db.delete("Stock Ledger Entry", {"item": self.item})

	def test_exact_cancellation_and_restored_layers(self):
		for method in ("Moving Average", "FIFO", "LIFO"):
			with self.subTest(method=method):
				self.clear_ledger()
				self.set_item_valuation_method(method)
				self.submit_entry("Receipt", 10, 20)
				self.submit_entry("Receipt", 10, 30)
				consume = self.submit_entry("Consume", 4)
				consume.cancel()
				self.assertEqual(tuple(self.get_balance(self.shelf_a)), (20, 500))
				# A cancellation posts now, so the next entry must also use a current time.
				transfer = self.submit_entry("Transfer", 12, target=self.shelf_b)
				expected = {"Moving Average": 300, "FIFO": 260, "LIFO": 340}[method]
				self.assertAlmostEqual(self.get_balance(self.shelf_b)[1], expected)
				transfer.cancel()
				self.assertEqual(tuple(self.get_balance(self.shelf_a)), (20, 500))
				self.assertEqual(tuple(self.get_balance(self.shelf_b)), (0, 0))
				originals = frappe.get_all(
					"Stock Ledger Entry",
					filters={"stock_entry": transfer.name, "reversal_of": ["is", "not set"]},
					fields=["name", "actual_quantity", "stock_value"],
				)
				for original in originals:
					reversal = frappe.get_value(
						"Stock Ledger Entry",
						{"reversal_of": original.name},
						["actual_quantity", "stock_value"],
						as_dict=True,
					)
					self.assertEqual(reversal.actual_quantity, -original.actual_quantity)
					self.assertEqual(reversal.stock_value, -original.stock_value)

	def test_receipt_cancellation_uses_original_value(self):
		self.submit_entry("Receipt", 10, 20)
		latest = self.submit_entry("Receipt", 10, 30)
		latest.cancel()
		self.assertEqual(tuple(self.get_balance(self.shelf_a)), (10, 200))

	def test_cancel_requires_reverse_order_across_warehouses(self):
		receipt = self.submit_entry("Receipt", 10, 20)
		consume = self.submit_entry("Consume", 2)
		frappe.db.savepoint("cancel_order")
		with self.assertRaises(frappe.ValidationError):
			receipt.cancel()
		frappe.db.rollback(save_point="cancel_order")
		self.assertEqual(
			frappe.db.count("Stock Ledger Entry", {"item": self.item, "reversal_of": ["is", "set"]}), 0
		)
		consume.cancel()
		frappe.get_doc("Stock Entry", receipt.name).cancel()
		self.assertEqual(tuple(self.get_balance(self.shelf_a)), (0, 0))

	def test_backdated_and_future_submissions_are_rejected(self):
		self.submit_entry("Receipt", 10, 20)
		for date in (add_days(today(), -1), add_days(today(), 1)):
			with self.subTest(date=date):
				entry = self.create_stock_entry("Receipt", 1, target_warehouse=self.shelf_a)
				entry.posting_date = date
				entry.insert(ignore_permissions=True)
				with self.assertRaises(frappe.ValidationError):
					entry.submit()
		self.assertEqual(tuple(self.get_balance(self.shelf_a)), (10, 200))

	def test_same_timestamp_is_allowed_and_creation_orders_layers(self):
		first = self.submit_entry("Receipt", 10, 20)
		second = self.create_stock_entry("Receipt", 10, target_warehouse=self.shelf_a, rate=30)
		second.posting_date, second.posting_time = first.posting_date, first.posting_time
		second.insert(ignore_permissions=True)
		second.submit()
		self.assertEqual(tuple(self.get_balance(self.shelf_a)), (20, 500))

	def test_method_changes_with_history_are_rejected(self):
		self.submit_entry("Receipt", 10, 20)
		self.set_item_valuation_method("FIFO")
		with self.assertRaises(frappe.ValidationError):
			self.submit_entry("Consume", 1)
		self.assertEqual(tuple(self.get_balance(self.shelf_a)), (10, 200))

	def test_mixed_entry_records_each_item_method(self):
		other = frappe.copy_doc(frappe.get_doc("Item", self.item))
		other.item_code = "TEST-SAFETY-FIFO"
		other.valuation_method = "FIFO"
		other.insert(ignore_permissions=True)
		entry = self.create_stock_entry("Receipt", 1, target_warehouse=self.shelf_a, rate=20)
		entry.append(
			"items", {"item": other.name, "target_warehouse": self.shelf_a, "quantity": 1, "rate": 30}
		)
		entry.insert(ignore_permissions=True)
		entry.submit()
		saved = frappe.get_doc("Stock Entry", entry.name)
		self.assertEqual(saved.valuation_method_used, "Mixed (see items)")
		self.assertEqual([row.valuation_method_used for row in saved.items], ["Moving Average", "FIFO"])
		self.assertEqual(
			set(
				frappe.get_all(
					"Stock Ledger Entry", filters={"stock_entry": entry.name}, pluck="valuation_method"
				)
			),
			{"Moving Average", "FIFO"},
		)

	def test_stock_balance_filters_and_default_date(self):
		self.submit_entry("Receipt", 10, 20)
		self.submit_entry("Transfer", 3, target=self.shelf_b)
		for filters, expected in (
			({"warehouse": self.shelf_b}, 3),
			({"warehouse": self.shelf_b, "item": self.item}, 3),
			({"warehouse": self.shelf_a, "as_of_date": add_days(today(), -1)}, None),
		):
			with self.subTest(filters=filters):
				_, data = stock_balance.execute(filters)
				rows = [row for row in data if row.item == self.item]
				if expected is None:
					self.assertFalse(rows)
				else:
					self.assertEqual(len(rows), 1)
					self.assertEqual(rows[0].quantity, expected)

	def test_ledger_report_opening_and_closing(self):
		self.submit_entry("Receipt", 10, 20)
		_, rows = stock_ledger.execute({"item": self.item, "warehouse": self.shelf_a})
		self.assertEqual(rows[0]["qty_after_transaction"], 0)
		self.assertEqual(rows[-1]["qty_after_transaction"], 10)
		with self.assertRaises(frappe.ValidationError):
			stock_ledger.execute(
				{
					"item": self.item,
					"warehouse": self.shelf_a,
					"from_date": today(),
					"to_date": add_days(today(), -1),
				}
			)

	def test_ledger_is_immutable_even_with_permission_bypass(self):
		entry = self.submit_entry("Receipt", 10, 20)
		ledger = frappe.get_doc("Stock Ledger Entry", {"stock_entry": entry.name})
		ledger.stock_value = 999
		with self.assertRaises(frappe.ValidationError):
			ledger.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Stock Ledger Entry", ledger.name, ignore_permissions=True, force=True)
		with self.assertRaises(frappe.ValidationError):
			frappe.copy_doc(ledger).insert(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Stock Ledger Entry", ledger.name, "stock_value"), 200)

	def test_concurrent_withdrawals_cannot_overdraw(self):
		self.submit_entry("Receipt", 10, 20)
		drafts = []
		posting_time = nowtime()
		for _ in range(2):
			entry = self.create_stock_entry("Consume", 7, source_warehouse=self.shelf_a)
			entry.posting_time = posting_time
			entry.insert(ignore_permissions=True)
			drafts.append(entry.name)
		frappe.db.commit()  # Independent worker connections must see fixtures and draft names.
		site, sites_path = frappe.local.site, frappe.local.sites_path
		barrier = Barrier(2)

		def withdraw(name):
			frappe.init(site=site, sites_path=sites_path)
			frappe.connect()
			frappe.set_user("Administrator")
			try:
				# Establish a snapshot before either worker acquires the item lock.
				frappe.db.sql("SELECT name FROM `tabStock Ledger Entry` WHERE item = %s", self.item)
				entry = frappe.get_doc("Stock Entry", name)
				barrier.wait(timeout=30)
				entry.submit()
				frappe.db.commit()
				return "submitted"
			except frappe.ValidationError as error:
				frappe.db.rollback()
				return str(error)
			finally:
				frappe.destroy()

		with ThreadPoolExecutor(max_workers=2) as pool:
			results = list(pool.map(withdraw, drafts))
		frappe.db.rollback()  # Discard the main connection's snapshot.
		self.assertEqual(results.count("submitted"), 1)
		self.assertTrue(any("Not enough stock" in result for result in results), results)
		self.assertEqual(tuple(self.get_balance(self.shelf_a)), (3, 60))
