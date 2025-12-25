# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Tax(Document):
	def validate(self):
		self.validate_template()

	def validate_template(self):
		"""Validate template fields based on is_template checkbox"""
		if self.is_template:
			if not self.template_name:
				frappe.throw(frappe._("Template Name is required when Is Template is checked"))
		else:
			if self.template_name:
				frappe.throw(frappe._("Template Name should be empty when Is Template is not checked"))
