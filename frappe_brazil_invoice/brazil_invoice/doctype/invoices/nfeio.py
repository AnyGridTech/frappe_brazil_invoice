# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

"""
NFe.io Tax Calculation API Integration

This module handles tax calculations (ICMS, IPI, PIS, COFINS) using the NFe.io API.
API Documentation: https://nfe.io/docs/desenvolvedores/rest-api/calculo-de-impostos-v1/

Configuration:
- Set 'nfeio_api_key' in site_config.json
- Set 'nfeio_company_id' in site_config.json
"""

import frappe
import requests


def calculate_taxes(invoice_doc, tax_template):
	"""
	Calculate ICMS and IPI using NFe.io Tax Calculation API
	
	Args:
		invoice_doc: Invoice document instance
		tax_template: Tax template document with calculation settings
	
	API Reference: 
		https://nfe.io/docs/desenvolvedores/rest-api/calculo-de-impostos-v1/calcula-os-impostos-de-uma-operacao/
	
	The API calculates all taxes (ICMS, IPI, PIS, COFINS) based on:
	- NCM code
	- Origin and destination states
	- Item values
	- Operation type (CFOP)
	"""
	if not invoice_doc.invoice_items_table:
		return
	
	# Get NFe.io API credentials from site config
	nfeio_api_key = frappe.conf.get("nfeio_api_key")
	nfeio_company_id = frappe.conf.get("nfeio_company_id")
	
	if not nfeio_api_key or not nfeio_company_id:
		frappe.log_error(
			"NFe.io API credentials not configured. Set 'nfeio_api_key' and 'nfeio_company_id' in site_config.json",
			"Tax Calculation Error"
		)
		# Fall back to hardcoded calculation
		calculate_taxes_fallback(invoice_doc, tax_template)
		return
	
	try:
		# Get company state for origin
		company_state = _get_company_state()
		
		# Destination state
		destination_state = invoice_doc.delivery_state or "SP"
		
		# Prepare items for API call
		items_for_calculation = _prepare_items_for_api(invoice_doc)
		
		if not items_for_calculation:
			return
		
		# Build API payload
		payload = _build_api_payload(
			invoice_doc,
			tax_template,
			company_state,
			destination_state,
			items_for_calculation
		)
		
		# Call NFe.io Tax Calculation API
		result = _call_nfeio_api(nfeio_api_key, nfeio_company_id, payload)
		
		if result:
			# Update invoice with calculated tax values
			_update_invoice_with_tax_values(invoice_doc, tax_template, result)
		else:
			# API call failed, use fallback
			calculate_taxes_fallback(invoice_doc, tax_template)
			
	except requests.exceptions.Timeout:
		frappe.log_error("NFe.io API request timed out", "Tax Calculation Timeout")
		calculate_taxes_fallback(invoice_doc, tax_template)
	except requests.exceptions.ConnectionError:
		frappe.log_error("Could not connect to NFe.io API", "Tax Calculation Connection Error")
		calculate_taxes_fallback(invoice_doc, tax_template)
	except Exception as e:
		frappe.log_error(
			f"Error calculating taxes with NFe.io: {str(e)}\n{frappe.get_traceback()}",
			"Tax Calculation Error"
		)
		calculate_taxes_fallback(invoice_doc, tax_template)


def calculate_taxes_fallback(invoice_doc, tax_template):
	"""
	Fallback tax calculation using hardcoded rates when NFe.io API is unavailable
	
	Args:
		invoice_doc: Invoice document instance
		tax_template: Tax template document with calculation settings
	
	IPI Rates by NCM:
	- 85044090 (INVERSOR): 9.75%
	- 85049090 (INSUMOS): 6.50%
	- 85437099 (SMART ENERGY): 6.50%
	"""
	if not invoice_doc.invoice_items_table:
		return
	
	# Determine if interstate operation
	company_state = _get_company_state()
	destination_state = invoice_doc.delivery_state or "SP"
	is_interstate = company_state != destination_state
	
	# Calculate ICMS
	if tax_template.calculate_automatically_icms:
		_calculate_icms_fallback(invoice_doc, tax_template, is_interstate)
	
	# Calculate IPI
	if tax_template.calculate_automatically_ipi:
		_calculate_ipi_fallback(invoice_doc, tax_template)


# Private helper functions

def _get_company_state():
	"""Get company state from default company settings"""
	# TODO: Fetch from Company doctype
	return "SP"  # Default to São Paulo


def _prepare_items_for_api(invoice_doc):
	"""Prepare invoice items in the format expected by NFe.io API"""
	items_for_calculation = []
	
	for item in invoice_doc.invoice_items_table:
		ncm = (item.ncm or "").replace(".", "").replace("-", "").strip()
		if not ncm:
			continue
		
		item_data = {
			"codigo": item.item_code,
			"descricao": item.item_name or item.item_code,
			"ncm": ncm,
			"quantidade": float(item.quantity or 1),
			"valorUnitario": float(item.rate or 0),
			"valorTotal": float(item.amount or 0)
		}
		items_for_calculation.append(item_data)
	
	return items_for_calculation


def _build_api_payload(invoice_doc, tax_template, company_state, destination_state, items):
	"""Build the payload for NFe.io API request"""
	payload = {
		"ufOrigem": company_state,
		"ufDestino": destination_state,
		"tipoCliente": "J" if len(invoice_doc.client_id_number or "") == 14 else "F",  # J=CNPJ, F=CPF
		"itens": items
	}
	
	# Add additional values if configured in template
	if tax_template.add_freight_icms and invoice_doc.total_freight:
		payload["valorFrete"] = float(invoice_doc.total_freight or 0)
	if tax_template.add_insurance_icms and invoice_doc.total_insurance:
		payload["valorSeguro"] = float(invoice_doc.total_insurance or 0)
	if tax_template.add_other_expenses_icms and invoice_doc.other_expenses:
		payload["valorOutrasDespesas"] = float(invoice_doc.other_expenses or 0)
	
	return payload


def _call_nfeio_api(api_key, company_id, payload):
	"""Make the API call to NFe.io tax calculation endpoint"""
	api_url = f"https://api.nfe.io/v1/companies/{company_id}/tax/calculate"
	
	response = requests.post(
		api_url,
		json=payload,
		headers={
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json"
		},
		timeout=10
	)
	
	if response.status_code == 200:
		return response.json()
	else:
		frappe.log_error(
			f"NFe.io API returned status {response.status_code}: {response.text}",
			"Tax Calculation API Error"
		)
		return None


def _update_invoice_with_tax_values(invoice_doc, tax_template, result):
	"""Update invoice document with calculated tax values from API response"""
	# NFe.io returns totals for ICMS, IPI, PIS, COFINS
	if tax_template.calculate_automatically_icms:
		icms_total = result.get("icms", {})
		if hasattr(invoice_doc, 'icms_base'):
			invoice_doc.icms_base = float(icms_total.get("baseCalculo", 0))
		if hasattr(invoice_doc, 'icms_rate'):
			invoice_doc.icms_rate = float(icms_total.get("aliquota", 0))
		if hasattr(invoice_doc, 'icms_value'):
			invoice_doc.icms_value = float(icms_total.get("valor", 0))
	
	if tax_template.calculate_automatically_ipi:
		ipi_total = result.get("ipi", {})
		if hasattr(invoice_doc, 'ipi_base'):
			invoice_doc.ipi_base = float(ipi_total.get("baseCalculo", 0))
		if hasattr(invoice_doc, 'ipi_rate'):
			invoice_doc.ipi_rate = float(ipi_total.get("aliquota", 0))
		if hasattr(invoice_doc, 'ipi_value'):
			invoice_doc.ipi_value = float(ipi_total.get("valor", 0))


def _calculate_icms_fallback(invoice_doc, tax_template, is_interstate):
	"""Calculate ICMS using hardcoded rates as fallback"""
	icms_rate = 12.0 if is_interstate else 18.0
	icms_base = 0.0
	
	for item in invoice_doc.invoice_items_table:
		icms_base += float(item.amount or 0)
	
	# Add additional values to base if configured
	if tax_template.add_freight_icms and invoice_doc.total_freight:
		icms_base += float(invoice_doc.total_freight or 0)
	if tax_template.add_insurance_icms and invoice_doc.total_insurance:
		icms_base += float(invoice_doc.total_insurance or 0)
	if tax_template.add_other_expenses_icms and invoice_doc.other_expenses:
		icms_base += float(invoice_doc.other_expenses or 0)
	
	icms_value = icms_base * (icms_rate / 100)
	
	if hasattr(invoice_doc, 'icms_base'):
		invoice_doc.icms_base = icms_base
	if hasattr(invoice_doc, 'icms_rate'):
		invoice_doc.icms_rate = icms_rate
	if hasattr(invoice_doc, 'icms_value'):
		invoice_doc.icms_value = icms_value


def _calculate_ipi_fallback(invoice_doc, tax_template):
	"""Calculate IPI using hardcoded NCM rates as fallback"""
	ipi_rates = {
		"85044090": 9.75,
		"8504.40.90": 9.75,
		"85049090": 6.50,
		"8504.90.90": 6.50,
		"85437099": 6.50,
		"8543.70.99": 6.50
	}
	
	ipi_base = 0.0
	ipi_value = 0.0
	
	for item in invoice_doc.invoice_items_table:
		item_value = float(item.amount or 0)
		ncm = (item.ncm or "").replace(".", "").replace("-", "").strip()
		ipi_rate = ipi_rates.get(ncm, 0.0)
		
		if ipi_rate > 0:
			ipi_base += item_value
			ipi_value += item_value * (ipi_rate / 100)
	
	if hasattr(invoice_doc, 'ipi_base'):
		invoice_doc.ipi_base = ipi_base
	if hasattr(invoice_doc, 'ipi_rate'):
		invoice_doc.ipi_rate = (ipi_value / ipi_base * 100) if ipi_base > 0 else 0
	if hasattr(invoice_doc, 'ipi_value'):
		invoice_doc.ipi_value = ipi_value
