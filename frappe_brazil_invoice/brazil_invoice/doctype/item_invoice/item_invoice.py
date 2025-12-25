# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ItemInvoice(Document):
	def before_insert(self):
		"""Auto-fill fields before inserting the document"""
		self._auto_fill_from_serial_number()
		self._calculate_amount()
	
	def validate(self):
		"""Validate item invoice and enforce rules"""
		self._auto_fill_from_serial_number()
		self._calculate_amount()
	
	def _auto_fill_from_serial_number(self):
		"""Auto-fill fields from serial number and item"""
		# If serial number is provided, auto-fill from serial number and item
		if self.serial_number:
			# Enforce quantity = 1 for serial numbers
			if self.quantity and self.quantity != 1:
				frappe.throw(_("Quantity must be 1 when Serial Number is provided. Serial numbers are unique and cannot have multiple quantities."))
			self.quantity = 1
			
			# Auto-fill item_code and item_name from serial number
			if not self.item_code:
				serial_doc = frappe.get_doc("Serial No", self.serial_number)
				self.item_code = serial_doc.item_code
				
			# Auto-fill remaining fields from item
			if self.item_code:
				item_doc = frappe.get_doc("Item", self.item_code)
				if not self.item_name:
					self.item_name = item_doc.item_name
				if not self.rate:
					self.rate = item_doc.valuation_rate or item_doc.standard_rate
				if not self.ncm:
					self.ncm = item_doc.get("ncm")
				if not self.description:
					self.description = item_doc.description or item_doc.item_name
	
	def _calculate_amount(self):
		"""Auto-calculate amount from rate and quantity"""
		if self.rate and self.quantity:
			self.amount = self.rate * self.quantity
