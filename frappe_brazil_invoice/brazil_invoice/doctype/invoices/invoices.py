# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
import requests
import json

class Invoices(Document):
	def on_update(self):
		frappe.log_error(f"Invoice document updated: {self.name}")

@frappe.whitelist()
def process_invoice(invoice_name):
	"""
	API endpoint to process and create NFe invoice via Go service
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

@frappe.whitelist(allow_guest=False)
def create_invoice(
	operation_type=None,
	client_type=None,
	freight_modality=None,
	client_name=None,
	client_email=None,
	client_phone=None,
	client_id_number=None,
	contribuinte_icms=None,
	inscricao_estadual=None,
	delivery_supervisor=None,
	delivery_cep=None,
	delivery_address=None,
	delivery_neighborhood=None,
	delivery_state=None,
	city=None,
	delivery_number_address=None,
	delivery_complement=None,
	delivery_ibge=None,
	delivery_phone=None,
	product_brand=None,
	product_quantity=None,
	product_type=None,
	carrier=None,
	product_gross_weight=None,
	product_net_weight=None,
	additional_information=None,
	total_freight=None,
	total_discount=None,
	total_insurance=None,
	other_expenses=None,
	total=None,
	total_tax=None,
	tax_template=None,
	invoices_table=None,
	nf_ref_serie=None,
	nf_ref_num=None,
	nf_ref_access_key=None,
	nf_de_retorno=None
):
	"""
	API endpoint for creating invoices from automation systems.
	
	This endpoint allows external automation systems to create invoices
	by sending the necessary parameters. The invoice will be created
	and saved in draft status.
	
	Args:
		operation_type (str): Type of operation (e.g., "Remessa para Conserto")
		client_type (str): Type of client
		freight_modality (str): Freight modality
		client_name (str): Client name or company name (required)
		client_email (str): Client email
		client_phone (str): Client phone number
		client_id_number (str): Client CPF or CNPJ (required)
		contribuinte_icms (str): ICMS contributor status
		inscricao_estadual (str): State registration number
		delivery_supervisor (str): Delivery supervisor name
		delivery_cep (str): Delivery postal code
		delivery_address (str): Delivery street address
		delivery_neighborhood (str): Delivery neighborhood
		delivery_state (str): Delivery state
		city (str): Delivery city
		delivery_number_address (str): Delivery address number
		delivery_complement (str): Delivery address complement
		delivery_ibge (str): IBGE city code
		delivery_phone (str): Delivery phone
		product_brand (str): Product brand
		product_quantity (str): Product quantity
		product_type (str): Product type/species
		carrier (str): Carrier name or ID
		product_gross_weight (str): Product gross weight
		product_net_weight (str): Product net weight
		additional_information (str): Additional information for the invoice
		total_freight (float): Total freight value
		total_discount (float): Total discount value
		total_insurance (float): Total insurance value
		other_expenses (float): Other expenses
		total (float): Total invoice value
		total_tax (float): Total tax value
		tax_template (str): Tax template name or ID
		invoices_table (list): List of invoice items (child table)
		nf_ref_serie (str): Reference NF series
		nf_ref_num (str): Reference NF number
		nf_ref_access_key (str): Reference NF access key
		nf_de_retorno (bool): Return NF flag
		
	Returns:
		dict: Response containing:
			- success (bool): Whether the operation was successful
			- docname (str): The name/ID of the created invoice document
			- message (str): Success or error message
	"""
	
	try:
		# Validate required fields
		required_fields = {
			"client_name": client_name,
			"client_id_number": client_id_number,
		}
		
		missing_fields = [field for field, value in required_fields.items() if not value]
		if missing_fields:
			return {
				"success": False,
				"message": f"Missing required fields: {', '.join(missing_fields)}",
				"docname": None
			}
		
		# Create new Invoice document
		invoice_doc = frappe.new_doc("Invoices")
		
		# Set basic fields
		if operation_type:
			invoice_doc.operation_type = operation_type
		if client_type:
			invoice_doc.client_type = client_type
		if freight_modality:
			invoice_doc.freight_modality = freight_modality
			
		# Set client information
		invoice_doc.client_name = client_name
		if client_email:
			invoice_doc.client_email = client_email
		if client_phone:
			invoice_doc.client_phone = client_phone
		invoice_doc.client_id_number = client_id_number
		if contribuinte_icms:
			invoice_doc.contribuinte_icms = contribuinte_icms
		if inscricao_estadual:
			invoice_doc.inscricao_estadual = inscricao_estadual
			
		# Set delivery information
		if delivery_supervisor:
			invoice_doc.delivery_supervisor = delivery_supervisor
		if delivery_cep:
			invoice_doc.delivery_cep = delivery_cep
		if delivery_address:
			invoice_doc.delivery_address = delivery_address
		if delivery_neighborhood:
			invoice_doc.delivery_neighborhood = delivery_neighborhood
		if delivery_state:
			invoice_doc.delivery_state = delivery_state
		if city:
			invoice_doc.city = city
		if delivery_number_address:
			invoice_doc.delivery_number_address = delivery_number_address
		if delivery_complement:
			invoice_doc.delivery_complement = delivery_complement
		if delivery_ibge:
			invoice_doc.delivery_ibge = delivery_ibge
		if delivery_phone:
			invoice_doc.delivery_phone = delivery_phone
			
		# Set product information
		if product_brand:
			invoice_doc.product_brand = product_brand
		if product_quantity:
			invoice_doc.product_quantity = product_quantity
		if product_type:
			invoice_doc.product_type = product_type
		if carrier:
			invoice_doc.carrier = carrier
		if product_gross_weight:
			invoice_doc.product_gross_weight = product_gross_weight
		if product_net_weight:
			invoice_doc.product_net_weight = product_net_weight
			
		# Set additional information
		if additional_information:
			invoice_doc.additional_information = additional_information
			
		# Set totals
		if total_freight:
			invoice_doc.total_freight = total_freight
		if total_discount:
			invoice_doc.total_discount = total_discount
		if total_insurance:
			invoice_doc.total_insurance = total_insurance
		if other_expenses:
			invoice_doc.other_expenses = other_expenses
		if total:
			invoice_doc.total = total
		if total_tax:
			invoice_doc.total_tax = total_tax
			
		# Set tax template
		if tax_template:
			invoice_doc.tax_template = tax_template
			
		# Set reference NF information
		if nf_ref_serie:
			invoice_doc.nf_ref_serie = nf_ref_serie
		if nf_ref_num:
			invoice_doc.nf_ref_num = nf_ref_num
		if nf_ref_access_key:
			invoice_doc.nf_ref_access_key = nf_ref_access_key
		if nf_de_retorno is not None:
			invoice_doc.nf_de_retorno = nf_de_retorno
			
		# Add invoice items (child table)
		if invoices_table:
			if isinstance(invoices_table, str):
				invoices_table = json.loads(invoices_table)
			
			for item in invoices_table:
				invoice_doc.append("invoices_table", item)
		
		# Insert the document (creates in Draft state)
		invoice_doc.insert(ignore_permissions=False)
		
		# Commit the transaction
		frappe.db.commit()
		
		return {
			"success": True,
			"docname": invoice_doc.name,
			"message": f"Invoice {invoice_doc.name} created successfully in draft state"
		}
		
	except frappe.ValidationError as e:
		frappe.db.rollback()
		frappe.log_error(
			title="Invoice Creation Validation Error",
			message=frappe.get_traceback()
		)
		return {
			"success": False,
			"message": str(e),
			"docname": None
		}
		
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(
			title="Invoice Creation Error",
			message=frappe.get_traceback()
		)
		return {
			"success": False,
			"message": f"An error occurred while creating the invoice: {str(e)}",
			"docname": None
		}

@frappe.whitelist(allow_guest=False)
def get_invoice_details(docname):
	"""
	Get details of an existing invoice document.
	
	Args:
		docname (str): The name/ID of the invoice document
		
	Returns:
		dict: Response containing:
			- success (bool): Whether the operation was successful
			- invoice (dict): Invoice document data
			- message (str): Success or error message
	"""
	try:
		if not docname:
			return {
				"success": False,
				"message": "Invoice docname is required",
				"invoice": None
			}
		
		# Check if invoice exists
		if not frappe.db.exists("Invoices", docname):
			return {
				"success": False,
				"message": f"Invoice {docname} does not exist",
				"invoice": None
			}
		
		# Get the invoice document
		invoice_doc = frappe.get_doc("Invoices", docname)
		
		# Check permissions
		if not invoice_doc.has_permission("read"):
			return {
				"success": False,
				"message": "You do not have permission to read this invoice",
				"invoice": None
			}
		
		return {
			"success": True,
			"invoice": invoice_doc.as_dict(),
			"message": f"Invoice {docname} retrieved successfully"
		}
		
	except Exception as e:
		frappe.log_error(
			title="Get Invoice Details Error",
			message=frappe.get_traceback()
		)
		return {
			"success": False,
			"message": f"An error occurred: {str(e)}",
			"invoice": None
		}

@frappe.whitelist(allow_guest=False)
def update_invoice_status(docname, invoice_id=None, invoice_link=None, invoice_number=None, invoice_serie=None):
	"""
	Update invoice status after processing (e.g., after NFe.io processing).
	
	Note: This function is similar to what process_invoice does,
	but it's kept separate for API use cases where you need to update
	invoice fields without going through NFe.io.
	
	Args:
		docname (str): The name/ID of the invoice document
		invoice_id (str): External invoice ID from NFe.io or similar service
		invoice_link (str): Link to the invoice PDF or external resource
		invoice_number (str): Invoice number assigned by the fiscal authority
		invoice_serie (str): Invoice series
		
	Returns:
		dict: Response containing:
			- success (bool): Whether the operation was successful
			- message (str): Success or error message
			- docname (str): The invoice docname
	"""
	try:
		if not docname:
			return {
				"success": False,
				"message": "Invoice docname is required"
			}
		
		# Check if invoice exists
		if not frappe.db.exists("Invoices", docname):
			return {
				"success": False,
				"message": f"Invoice {docname} does not exist"
			}
		
		# Get the invoice document
		invoice_doc = frappe.get_doc("Invoices", docname)
		
		# Update fields
		if invoice_id:
			invoice_doc.invoice_id = invoice_id
		if invoice_link:
			invoice_doc.invoice_link = invoice_link
		if invoice_number:
			invoice_doc.invoice_number = invoice_number
		if invoice_serie:
			invoice_doc.invoice_serie = invoice_serie
		
		# Save the document
		invoice_doc.save(ignore_permissions=False)
		frappe.db.commit()
		
		return {
			"success": True,
			"message": f"Invoice {docname} updated successfully",
			"docname": docname
		}
		
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(
			title="Update Invoice Status Error",
			message=frappe.get_traceback()
		)
		return {
			"success": False,
			"message": f"An error occurred: {str(e)}"
		}

@frappe.whitelist(allow_guest=False)
def bulk_create_invoices(invoices_data):
	"""
	Create multiple invoices in a single API call.
	
	Args:
		invoices_data (list): List of invoice data dictionaries, each containing
			the same parameters as create_invoice
			
	Returns:
		dict: Response containing:
			- success (bool): Whether all operations were successful
			- created_invoices (list): List of successfully created invoice docnames
			- failed_invoices (list): List of failed invoice creation attempts with errors
			- message (str): Summary message
			- total_processed (int): Total number of invoices processed
			- total_success (int): Number of successfully created invoices
			- total_failed (int): Number of failed invoice creations
	"""
	try:
		# Parse JSON string if needed
		if isinstance(invoices_data, str):
			try:
				invoices_data = json.loads(invoices_data)
			except json.JSONDecodeError:
				return {
					"success": False,
					"message": "invoices_data must be a list of invoice dictionaries",
					"created_invoices": [],
					"failed_invoices": []
				}
		
		if not isinstance(invoices_data, list):
			return {
				"success": False,
				"message": "invoices_data must be a list of invoice dictionaries",
				"created_invoices": [],
				"failed_invoices": []
			}
		
		created_invoices = []
		failed_invoices = []
		
		for idx, invoice_data in enumerate(invoices_data):
			try:
				# Call the single invoice creation function
				result = create_invoice(**invoice_data)
				
				if result.get("success"):
					created_invoices.append({
						"index": idx,
						"docname": result.get("docname")
					})
				else:
					failed_invoices.append({
						"index": idx,
						"error": result.get("message"),
						"data": invoice_data
					})
					
			except Exception as e:
				failed_invoices.append({
					"index": idx,
					"error": str(e),
					"data": invoice_data
				})
		
		success = len(failed_invoices) == 0
		
		return {
			"success": success,
			"created_invoices": created_invoices,
			"failed_invoices": failed_invoices,
			"message": f"Created {len(created_invoices)} invoices successfully, {len(failed_invoices)} failed",
			"total_processed": len(invoices_data),
			"total_success": len(created_invoices),
			"total_failed": len(failed_invoices)
		}
		
	except Exception as e:
		frappe.log_error(
			title="Bulk Create Invoices Error",
			message=frappe.get_traceback()
		)
		return {
			"success": False,
			"message": f"An error occurred: {str(e)}",
			"created_invoices": [],
			"failed_invoices": []
		}

@frappe.whitelist(allow_guest=False)
def bulk_process_invoices(invoice_names):
	"""
	Process multiple invoices through NFe.io in a single API call.
	
	Args:
		invoice_names (list): List of invoice docnames to process
			
	Returns:
		dict: Response containing:
			- success (bool): Whether all operations were successful
			- processed_invoices (list): List of successfully processed invoices with their data
			- failed_invoices (list): List of failed invoice processing attempts with errors
			- message (str): Summary message
			- total_processed (int): Total number of invoices attempted
			- total_success (int): Number of successfully processed invoices
			- total_failed (int): Number of failed invoice processing attempts
	"""
	try:
		# Parse JSON string if needed
		if isinstance(invoice_names, str):
			try:
				invoice_names = json.loads(invoice_names)
			except json.JSONDecodeError:
				return {
					"success": False,
					"message": "invoice_names must be a list of invoice docnames",
					"processed_invoices": [],
					"failed_invoices": []
				}
		
		if not isinstance(invoice_names, list):
			return {
				"success": False,
				"message": "invoice_names must be a list of invoice docnames",
				"processed_invoices": [],
				"failed_invoices": []
			}
		
		processed_invoices = []
		failed_invoices = []
		
		for idx, invoice_name in enumerate(invoice_names):
			try:
				# Call the single invoice processing function
				result = process_invoice(invoice_name)
				
				if result.get("success"):
					processed_invoices.append({
						"index": idx,
						"docname": invoice_name,
						"invoice_id": result.get("data", {}).get("id"),
						"invoice_link": result.get("data", {}).get("pdf")
					})
				else:
					failed_invoices.append({
						"index": idx,
						"docname": invoice_name,
						"error": result.get("message", "Unknown error")
					})
					
			except Exception as e:
				failed_invoices.append({
					"index": idx,
					"docname": invoice_name,
					"error": str(e)
				})
		
		success = len(failed_invoices) == 0
		
		return {
			"success": success,
			"processed_invoices": processed_invoices,
			"failed_invoices": failed_invoices,
			"message": f"Processed {len(processed_invoices)} invoices successfully, {len(failed_invoices)} failed",
			"total_processed": len(invoice_names),
			"total_success": len(processed_invoices),
			"total_failed": len(failed_invoices)
		}
		
	except Exception as e:
		frappe.log_error(
			title="Bulk Process Invoices Error",
			message=frappe.get_traceback()
		)
		return {
			"success": False,
			"message": f"An error occurred: {str(e)}",
			"processed_invoices": [],
			"failed_invoices": []
		}
