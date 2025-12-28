# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

"""
Product Invoice Operations for NFe.io API Integration

This module handles all product invoice (NFe) operations with the NFe.io API:
- Issue/Emit product invoices
- Cancel product invoices
- Query invoice events
- Retrieve PDF (DANFE)
- Retrieve XML

API Documentation: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/
"""

import json
import frappe
import requests
from requests.exceptions import Timeout, ConnectionError, RequestException


# NFe.io API Base URL
NFEIO_API_BASE_URL = "https://api.nfse.io/v2"


class NFeIOAPIError(Exception):
    """Custom exception for NFe.io API errors"""
    pass


def _make_api_request(method, endpoint, nfeio_config, data=None, params=None):
    """
    Make authenticated request to NFe.io API
    
    Args:
        method: HTTP method (GET, POST, DELETE)
        endpoint: API endpoint path
        nfeio_config: NFeIO document with configuration
        data: Request body data (for POST)
        params: Query parameters
        
    Returns:
        Response data as dict or None
        
    Raises:
        NFeIOAPIError: If API request fails
    """
    if not nfeio_config or not nfeio_config.api_token:
        raise NFeIOAPIError("NFe.io API token not configured")
    
    url = f"{NFEIO_API_BASE_URL}{endpoint}"
    
    headers = {
        "Authorization": nfeio_config.api_token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, params=params, timeout=30)
        else:
            raise NFeIOAPIError(f"Unsupported HTTP method: {method}")
        
        # Handle different status codes
        if response.status_code in [200, 202, 204]:
            # Success responses
            if response.status_code == 204:
                return None  # No content
            
            try:
                return response.json() if response.content else None
            except json.JSONDecodeError:
                return None
        elif response.status_code == 400:
            # Bad request
            error_msg = "Bad request"
            try:
                error_data = response.json()
                error_msg = error_data.get("message", str(error_data))
            except Exception:
                error_msg = response.text
            raise NFeIOAPIError(f"Bad request: {error_msg}")
        elif response.status_code == 404:
            raise NFeIOAPIError("Resource not found")
        elif response.status_code == 401:
            raise NFeIOAPIError("Authentication failed - Invalid API token")
        else:
            raise NFeIOAPIError(
                f"API request failed with status {response.status_code}: {response.text}"
            )
            
    except Timeout:
        raise NFeIOAPIError("API request timed out")
    except ConnectionError:
        raise NFeIOAPIError("Failed to connect to NFe.io API")
    except RequestException as e:
        raise NFeIOAPIError(f"Request error: {str(e)}")


def issue_product_invoice(invoice_data, nfeio_config):
    """
    Issue/Emit a product invoice (NFe) via NFe.io API
    
    This sends the invoice to the NFe.io queue for asynchronous processing.
    Use webhooks or query events to get the final status.
    
    Args:
        invoice_data: Dict containing the complete invoice data following NFe.io schema
        nfeio_config: NFeIO document with API configuration
        
    Returns:
        dict: Response from API with invoice details
        
    Raises:
        NFeIOAPIError: If API request fails
        
    API Endpoint: POST /v2/companies/{companyId}/productinvoices
    Documentation: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/emitir-uma-nota-fiscal-eletronica-nfe/
    """
    if not nfeio_config or not nfeio_config.company_id:
        raise NFeIOAPIError("Company ID not configured in NFeIO settings")
    
    endpoint = f"/companies/{nfeio_config.company_id}/productinvoices"
    
    try:
        response_data = _make_api_request("POST", endpoint, nfeio_config, data=invoice_data)
        
        frappe.logger().info(
            f"Product invoice issued successfully via NFe.io API. "
            f"Invoice ID: {response_data.get('id') if response_data else 'N/A'}"
        )
        
        return response_data
        
    except NFeIOAPIError as e:
        frappe.log_error(
            f"Failed to issue product invoice: {str(e)}\n"
            f"Invoice data: {json.dumps(invoice_data, indent=2)}",
            "NFe.io Issue Invoice Error"
        )
        raise


def cancel_product_invoice(invoice_id, reason, nfeio_config):
    """
    Cancel a product invoice (NFe) via NFe.io API
    
    This sends the invoice to the cancellation queue for asynchronous processing.
    Use webhooks or query events to get the final status.
    
    Args:
        invoice_id: NFe.io invoice ID to cancel
        reason: Cancellation reason (required)
        nfeio_config: NFeIO document with API configuration
        
    Returns:
        dict: Response from API (may be None for 204 status)
        
    Raises:
        NFeIOAPIError: If API request fails
        
    API Endpoint: DELETE /v2/companies/{companyId}/productinvoices/{invoiceId}
    Documentation: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/cancelar-uma-nota-fiscal-eletronica-nfe/
    """
    if not nfeio_config or not nfeio_config.company_id:
        raise NFeIOAPIError("Company ID not configured in NFeIO settings")
    
    if not invoice_id:
        raise NFeIOAPIError("Invoice ID is required for cancellation")
    
    if not reason:
        raise NFeIOAPIError("Cancellation reason is required")
    
    endpoint = f"/companies/{nfeio_config.company_id}/productinvoices/{invoice_id}"
    params = {"reason": reason}
    
    try:
        response_data = _make_api_request("DELETE", endpoint, nfeio_config, params=params)
        
        frappe.logger().info(
            f"Product invoice cancellation queued successfully. "
            f"Invoice ID: {invoice_id}, Reason: {reason}"
        )
        
        return response_data or {"success": True, "message": "Cancellation queued"}
        
    except NFeIOAPIError as e:
        frappe.log_error(
            f"Failed to cancel product invoice: {str(e)}\n"
            f"Invoice ID: {invoice_id}, Reason: {reason}",
            "NFe.io Cancel Invoice Error"
        )
        raise


def get_product_invoice_by_id(invoice_id, nfeio_config):
    """
    Get a product invoice (NFe) by ID via NFe.io API
    
    Retrieves complete invoice details including status, items, taxes, and all metadata.
    
    Args:
        invoice_id: NFe.io invoice ID
        nfeio_config: NFeIO document with API configuration
        
    Returns:
        dict: Complete invoice data
        
    Raises:
        NFeIOAPIError: If API request fails
        
    API Endpoint: GET /v2/companies/{companyId}/productinvoices/{invoiceId}
    Documentation: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/consultar-por-id-uma-nota-fiscal-eletronica-nfe/
    """
    if not nfeio_config or not nfeio_config.company_id:
        raise NFeIOAPIError("Company ID not configured in NFeIO settings")
    
    if not invoice_id:
        raise NFeIOAPIError("Invoice ID is required")
    
    endpoint = f"/companies/{nfeio_config.company_id}/productinvoices/{invoice_id}"
    
    try:
        response_data = _make_api_request("GET", endpoint, nfeio_config)
        
        frappe.logger().info(
            f"Retrieved invoice {invoice_id}. "
            f"Status: {response_data.get('status', 'unknown') if response_data else 'no data'}"
        )
        
        return response_data
        
    except NFeIOAPIError as e:
        frappe.log_error(
            f"Failed to get product invoice: {str(e)}\n"
            f"Invoice ID: {invoice_id}",
            "NFe.io Get Invoice Error"
        )
        raise


def get_invoice_events(invoice_id, nfeio_config, limit=10, starting_after=0):
    """
    Query events for a product invoice (NFe) via NFe.io API
    
    Retrieves the event history for an invoice, useful for tracking processing status.
    
    Args:
        invoice_id: NFe.io invoice ID
        nfeio_config: NFeIO document with API configuration
        limit: Maximum number of events to retrieve (default: 10)
        starting_after: Pagination starting index (default: 0)
        
    Returns:
        dict: Response containing events array and pagination info
        
    Raises:
        NFeIOAPIError: If API request fails
        
    API Endpoint: GET /v2/companies/{companyId}/productinvoices/{invoiceId}/events
    Documentation: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/consultar-eventos-por-id-uma-nota-fiscal-eletronica-nfe/
    """
    if not nfeio_config or not nfeio_config.company_id:
        raise NFeIOAPIError("Company ID not configured in NFeIO settings")
    
    if not invoice_id:
        raise NFeIOAPIError("Invoice ID is required")
    
    endpoint = f"/companies/{nfeio_config.company_id}/productinvoices/{invoice_id}/events"
    params = {
        "limit": limit,
        "startingAfter": starting_after
    }
    
    try:
        response_data = _make_api_request("GET", endpoint, nfeio_config, params=params)
        
        frappe.logger().info(
            f"Retrieved events for invoice {invoice_id}. "
            f"Events count: {len(response_data.get('events', []))}"
        )
        
        return response_data
        
    except NFeIOAPIError as e:
        frappe.log_error(
            f"Failed to get invoice events: {str(e)}\n"
            f"Invoice ID: {invoice_id}",
            "NFe.io Get Events Error"
        )
        raise


def get_invoice_pdf(invoice_id, nfeio_config, force=False):
    """
    Get PDF URL for invoice auxiliary document (DANFE) via NFe.io API
    
    Retrieves the URL to download the DANFE (Documento Auxiliar da Nota Fiscal Eletrônica) PDF.
    
    Args:
        invoice_id: NFe.io invoice ID
        nfeio_config: NFeIO document with API configuration
        force: Force PDF generation regardless of FlowStatus (default: False)
        
    Returns:
        dict: Response containing PDF URI
        
    Raises:
        NFeIOAPIError: If API request fails
        
    API Endpoint: GET /v2/companies/{companyId}/productinvoices/{invoiceId}/pdf
    Documentation: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/consultar-pdf-do-documento-auxiliar-da-nota-fiscal-eletronica-danfe/
    """
    if not nfeio_config or not nfeio_config.company_id:
        raise NFeIOAPIError("Company ID not configured in NFeIO settings")
    
    if not invoice_id:
        raise NFeIOAPIError("Invoice ID is required")
    
    endpoint = f"/companies/{nfeio_config.company_id}/productinvoices/{invoice_id}/pdf"
    params = {"force": str(force).lower()}
    
    try:
        response_data = _make_api_request("GET", endpoint, nfeio_config, params=params)
        
        frappe.logger().info(
            f"Retrieved PDF URL for invoice {invoice_id}. "
            f"URL: {response_data.get('uri') if response_data else 'N/A'}"
        )
        
        return response_data
        
    except NFeIOAPIError as e:
        frappe.log_error(
            f"Failed to get invoice PDF: {str(e)}\n"
            f"Invoice ID: {invoice_id}",
            "NFe.io Get PDF Error"
        )
        raise


def get_invoice_xml(invoice_id, nfeio_config):
    """
    Get XML URL for product invoice (NFe) via NFe.io API
    
    Retrieves the URL to download the official NFe XML document.
    
    Args:
        invoice_id: NFe.io invoice ID
        nfeio_config: NFeIO document with API configuration
        
    Returns:
        dict: Response containing XML URI
        
    Raises:
        NFeIOAPIError: If API request fails
        
    API Endpoint: GET /v2/companies/{companyId}/productinvoices/{invoiceId}/xml
    Documentation: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/consultar-xml-da-nota-fiscal-eletronica-nfe/
    """
    if not nfeio_config or not nfeio_config.company_id:
        raise NFeIOAPIError("Company ID not configured in NFeIO settings")
    
    if not invoice_id:
        raise NFeIOAPIError("Invoice ID is required")
    
    endpoint = f"/companies/{nfeio_config.company_id}/productinvoices/{invoice_id}/xml"
    
    try:
        response_data = _make_api_request("GET", endpoint, nfeio_config)
        
        frappe.logger().info(
            f"Retrieved XML URL for invoice {invoice_id}. "
            f"URL: {response_data.get('uri') if response_data else 'N/A'}"
        )
        
        return response_data
        
    except NFeIOAPIError as e:
        frappe.log_error(
            f"Failed to get invoice XML: {str(e)}\n"
            f"Invoice ID: {invoice_id}",
            "NFe.io Get XML Error"
        )
        raise


def build_invoice_payload(invoice_doc):
    """
    Build NFe.io API payload from Product Invoice document
    
    Converts a Frappe Product Invoice document to the NFe.io API format.
    This is a basic implementation that should be extended based on your
    specific Product Invoice doctype structure.
    
    Args:
        invoice_doc: Product Invoice Frappe document
        
    Returns:
        dict: Invoice data in NFe.io API format
    """
    # Basic payload structure - extend based on your Product Invoice doctype
    payload = {
        "operationNature": invoice_doc.get("operation_nature") or "VENDA",
        "operationType": "Outgoing",  # or "Incoming"
        "consumerType": "FinalConsumer",  # or "Normal"
        "items": [],
        "buyer": {},
        "totals": {
            "icms": {}
        }
    }
    
    # Add buyer information if available
    if invoice_doc.get("customer"):
        payload["buyer"] = {
            "name": invoice_doc.get("customer_name"),
            "federalTaxNumber": invoice_doc.get("customer_tax_id"),
            # Add more buyer details as needed
        }
    
    # Add items from invoice
    if invoice_doc.get("items"):
        for item in invoice_doc.items:
            payload["items"].append({
                "code": item.get("item_code"),
                "description": item.get("description"),
                "quantity": item.get("qty", 0),
                "unitAmount": item.get("rate", 0),
                "totalAmount": item.get("amount", 0),
                "cfop": item.get("cfop"),
                "ncm": item.get("ncm"),
                # Add tax details
                "tax": {
                    "icms": {},
                    "pis": {},
                    "cofins": {},
                }
            })
    
    # Add totals
    if invoice_doc.get("total_amount"):
        payload["totals"]["icms"]["productAmount"] = invoice_doc.total_amount
        payload["totals"]["icms"]["invoiceAmount"] = invoice_doc.total_amount
    
    return payload
