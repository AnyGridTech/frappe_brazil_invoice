# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests
import json

class Invoices(Document):
	def on_update(self):
		frappe.log_error(f"Invoice document updated: {self.name}")

	def create_invoice(self):
		"""
		Deprecated method - use create_nfe_invoice API endpoint instead
		"""
		pass


@frappe.whitelist()
def create_nfe_invoice(invoice_name):
	"""
	API endpoint to create NFe invoice via Go service
	This is called from the form button
	"""
	try:
		# Get Go API endpoint from site config
		go_api_url = frappe.conf.get("nfe_go_api_url", "http://localhost:3000")
		
		# Call Go service to create invoice
		response = requests.post(
			f"{go_api_url}/issue",
			json={"invoice_id": invoice_name},
			headers={"Content-Type": "application/json"},
			timeout=30
		)
		
		if response.status_code == 200:
			result = response.json()
			
			# Update invoice with NFe.io response
			invoice_doc = frappe.get_doc("Invoices", invoice_name)
			invoice_doc.invoice_id = result.get("id")
			invoice_doc.invoice_link = result.get("pdf")
			invoice_doc.db_update()
			
			frappe.db.commit()
			
			frappe.msgprint(
				f"Invoice created successfully!<br>"
				f"ID: {result.get('id')}<br>"
				f"Status: {result.get('status')}<br>"
				f"<a href='{result.get('pdf')}' target='_blank'>View PDF</a>",
				title="Success",
				indicator="green"
			)
			
			return {
				"success": True,
				"message": "Invoice created successfully",
				"data": result
			}
		else:
			error_msg = f"Go API returned status {response.status_code}: {response.text}"
			frappe.log_error(error_msg, "NFe Invoice Creation Error")
			frappe.throw(f"Failed to create invoice: {error_msg}")
			
	except requests.exceptions.Timeout:
		frappe.throw("Request to Go API timed out. Please try again.")
	except requests.exceptions.ConnectionError:
		frappe.throw("Could not connect to Go API. Please ensure the service is running.")
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "NFe Invoice Creation Error")
		frappe.throw(f"An error occurred: {str(e)}")


@frappe.whitelist()
def get_invoice_status(invoice_name):
	"""
	Get the current status of an NFe invoice
	"""
	try:
		invoice_doc = frappe.get_doc("Invoices", invoice_name)
		
		if not invoice_doc.invoice_id:
			return {
				"success": False,
				"message": "Invoice has not been created yet"
			}
		
		go_api_url = frappe.conf.get("nfe_go_api_url", "http://localhost:3000")
		
		response = requests.get(
			f"{go_api_url}/invoice/{invoice_doc.invoice_id}",
			timeout=10
		)
		
		if response.status_code == 200:
			return {
				"success": True,
				"data": response.json()
			}
		else:
			return {
				"success": False,
				"message": f"API returned status {response.status_code}"
			}
			
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "NFe Status Check Error")
		return {
			"success": False,
			"message": str(e)
		}
