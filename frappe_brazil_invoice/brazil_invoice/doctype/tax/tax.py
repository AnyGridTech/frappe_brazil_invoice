# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Tax(Document):
	def validate(self):
		self.validate_template()
		self.validate_automatic_calculation()

	def validate_template(self):
		"""Validate template fields based on is_template checkbox"""
		if self.is_template:
			if not self.template_name:
				frappe.throw(frappe._("Template Name is required when Is Template is checked"))
		else:
			if self.template_name:
				frappe.throw(frappe._("Template Name should be empty when Is Template is not checked"))

	def validate_automatic_calculation(self):
		"""Validate that automatic calculation requires zero rates"""
		# ICMS validation
		if self.calculate_automatically_icms and self.icms_rate != 0:
			frappe.throw(frappe._("ICMS Rate must be 0 when Calculate Automatically is enabled"))
		
		# IPI validation
		if self.calculate_automatically_ipi and self.ipi_rate != 0:
			frappe.throw(frappe._("IPI Rate must be 0 when Calculate Automatically is enabled"))
		
		# COFINS validation
		if self.calculate_automatically_cofins and self.cofins_rate != 0:
			frappe.throw(frappe._("COFINS Rate must be 0 when Calculate Automatically is enabled"))
		
		# PIS validation
		if self.calculate_automatically_pis and self.pis_rate != 0:
			frappe.throw(frappe._("PIS Rate must be 0 when Calculate Automatically is enabled"))
