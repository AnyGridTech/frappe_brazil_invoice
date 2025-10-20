# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests

class Invoices(Document):
	def on_update(self):
		frappe.log_error(f"Invoice document updated: {self.name}")

	def create_invoice(self):
		url = "https://example.com/api/invoices"
		payload = {
#            "urlNf": self.table_invoice[0].invoice_link if self.table_invoice else "",
#            "numberNf": self.table_invoice[0].invoice_number if self.table_invoice else "",
		}
		headers = {
			"Content-Type": "application/json"
		}
		response = requests.post(url, json=payload, headers=headers)
		if response.status_code == 200:
			frappe.msgprint("Invoice sent successfully.")
		else:
			frappe.log_error(f"Failed to send invoice: {response.text}")

	pass
