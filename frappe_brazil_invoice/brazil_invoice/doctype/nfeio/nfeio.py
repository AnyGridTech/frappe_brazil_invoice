# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from . import tax


class NFeIO(Document):
    def validate(self):
        """Validate NFeIO document before saving"""
        self.validate_unique_api_token()

    def validate_unique_api_token(self):
        """Ensure API token is unique across all NFeIO documents"""
        if not self.api_token:
            return

        # Check if another document exists with the same API token
        existing = frappe.db.get_all(
            "NFeIO",
            filters={
                "api_token": self.api_token,
                "name": ["!=", self.name],
            },
            limit=1,
        )

        if existing:
            frappe.throw(
                "API Token already exists in another NFeIO configuration. "
                "Each configuration must have a unique API token.",
                frappe.ValidationError,
            )


@frappe.whitelist()
def calculate_invoice_taxes(invoice_name, tax_template_name, use_fallback=False):
    """
    API endpoint to calculate taxes for an invoice using NFe.io

    Args:
        invoice_name: Name of the Invoice document
        tax_template_name: Name of the Tax template to use
        use_fallback: Boolean to enable fallback to hardcoded rates if API fails (default: False)

    Returns:
        dict: Calculated tax values (icms_value, ipi_value, pis_value, cofins_value)
    """
    try:
        # Get invoice and tax template documents
        invoice_doc = frappe.get_doc("Product Invoice", invoice_name)
        tax_template = frappe.get_doc("Tax", tax_template_name)

        # Check for valid (non-test) NFe.io configuration
        nfeio_config = _get_valid_nfeio_config()

        if not nfeio_config:
            frappe.throw(
                "No valid NFe.io configuration found. Please create an NFeIO document with API credentials (is_test_config must be 0)."
            )

        # Calculate taxes
        tax.calculate_taxes(invoice_doc, tax_template, nfeio_config, use_fallback=use_fallback)

        # Return calculated values
        return {
            "success": True,
            "icms_value": invoice_doc.icms_value or 0,
            "ipi_value": invoice_doc.ipi_value or 0,
            "pis_value": invoice_doc.pis_value or 0,
            "cofins_value": invoice_doc.cofins_value or 0,
        }

    except Exception as e:
        frappe.log_error(
            f"Error calculating taxes for invoice {invoice_name}: {str(e)}\n{frappe.get_traceback()}",
            "Tax Calculation API Error",
        )
        return {
            "success": False,
            "error": str(e),
        }


@frappe.whitelist()
def get_nfeio_config():
    """
    API endpoint to get NFe.io configuration

    Returns:
        dict: NFe.io configuration (company_id, company_name, has_api_token)
    """
    try:
        nfeio_config = _get_nfeio_config()

        if not nfeio_config:
            return {
                "success": False,
                "configured": False,
                "message": "NFe.io configuration not found",
            }

        return {
            "success": True,
            "configured": True,
            "company_id": nfeio_config.company_id,
            "company_name": nfeio_config.company_name,
            "has_api_token": bool(nfeio_config.api_token),
        }

    except Exception as e:
        frappe.log_error(
            f"Error getting NFe.io configuration: {str(e)}\n{frappe.get_traceback()}",
            "NFe.io Configuration Error",
        )
        return {
            "success": False,
            "error": str(e),
        }


def _get_nfeio_config():
    """Helper function to get NFe.io configuration"""
    try:
        # Get the first NFeIO document (assuming single configuration)
        nfeio_list = frappe.get_all("NFeIO", limit=1)
        if nfeio_list:
            return frappe.get_doc("NFeIO", nfeio_list[0].name)
        return None
    except Exception:
        return None


def _get_valid_nfeio_config():
    """Helper function to get valid (non-test) NFe.io configuration"""
    try:
        # Get NFeIO documents where is_test_config is 0 or null
        nfeio_list = frappe.get_all(
            "NFeIO",
            filters=[["is_test_config", "in", [0, ""]]],
            limit=1
        )
        if nfeio_list:
            return frappe.get_doc("NFeIO", nfeio_list[0].name)
        return None
    except Exception:
        return None


# ============================================================================
# Product Invoice Operations - Whitelisted API Endpoints
# ============================================================================

@frappe.whitelist()
def issue_product_invoice(invoice_data):
    """
    API endpoint to issue/emit a product invoice (NFe) via NFe.io
    
    This queues the invoice for asynchronous processing. The response indicates
    successful queuing, not successful emission. Use webhooks or query_product_invoice_events
    to track the actual emission status.
    
    Args:
        invoice_data: JSON string or dict with invoice data in NFe.io format
        
    Returns:
        dict: Response with success status and invoice details
        
    Example:
        frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.issue_product_invoice",
            args: { invoice_data: {...} }
        })
    """
    from . import product_invoice
    
    try:
        # Parse invoice data if it's a JSON string
        if isinstance(invoice_data, str):
            import json
            invoice_data = json.loads(invoice_data)
        
        # Get valid NFe.io configuration
        nfeio_config = _get_valid_nfeio_config()
        if not nfeio_config:
            return {
                "success": False,
                "error": "No valid NFe.io configuration found. Please create an NFeIO document with API credentials."
            }
        
        # Issue the invoice
        response = product_invoice.issue_product_invoice(invoice_data, nfeio_config)
        
        return {
            "success": True,
            "data": response,
            "message": "Invoice queued for emission successfully"
        }
        
    except product_invoice.NFeIOAPIError as e:
        frappe.log_error(
            f"NFe.io API Error: {str(e)}\n{frappe.get_traceback()}",
            "Issue NFe API Error"
        )
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        frappe.log_error(
            f"Error issuing NFe: {str(e)}\n{frappe.get_traceback()}",
            "Issue NFe Error"
        )
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def cancel_product_invoice(invoice_id, reason):
    """
    API endpoint to cancel a product invoice (NFe) via NFe.io
    
    This queues the cancellation for asynchronous processing. Use webhooks or
    query_product_invoice_events to track the actual cancellation status.
    
    Args:
        invoice_id: NFe.io invoice ID to cancel
        reason: Cancellation reason (required, minimum length varies by state)
        
    Returns:
        dict: Response with success status
        
    Example:
        frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.cancel_product_invoice",
            args: {
                invoice_id: "abc123",
                reason: "Canceled by customer request"
            }
        })
    """
    from . import product_invoice
    
    try:
        # Validate inputs
        if not invoice_id:
            return {
                "success": False,
                "error": "Invoice ID is required"
            }
        
        if not reason:
            return {
                "success": False,
                "error": "Cancellation reason is required"
            }
        
        # Get valid NFe.io configuration
        nfeio_config = _get_valid_nfeio_config()
        if not nfeio_config:
            return {
                "success": False,
                "error": "No valid NFe.io configuration found"
            }
        
        # Cancel the invoice
        response = product_invoice.cancel_product_invoice(invoice_id, reason, nfeio_config)
        
        return {
            "success": True,
            "data": response,
            "message": "Invoice cancellation queued successfully"
        }
        
    except product_invoice.NFeIOAPIError as e:
        frappe.log_error(
            f"NFe.io API Error: {str(e)}\n{frappe.get_traceback()}",
            "Cancel NFe API Error"
        )
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        frappe.log_error(
            f"Error canceling NFe: {str(e)}\n{frappe.get_traceback()}",
            "Cancel NFe Error"
        )
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def query_product_invoice_events(invoice_id, limit=10, starting_after=0):
    """
    API endpoint to query events for a product invoice (NFe)
    
    Retrieves the event history for tracking invoice processing status.
    Events include emission, cancellation, authorization, rejection, etc.
    
    Args:
        invoice_id: NFe.io invoice ID
        limit: Maximum number of events to retrieve (default: 10)
        starting_after: Pagination starting index (default: 0)
        
    Returns:
        dict: Response with events array and pagination info
        
    Example:
        frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.query_product_invoice_events",
            args: {
                invoice_id: "abc123",
                limit: 20
            }
        })
    """
    from . import product_invoice
    
    try:
        # Validate input
        if not invoice_id:
            return {
                "success": False,
                "error": "Invoice ID is required"
            }
        
        # Get valid NFe.io configuration
        nfeio_config = _get_valid_nfeio_config()
        if not nfeio_config:
            return {
                "success": False,
                "error": "No valid NFe.io configuration found"
            }
        
        # Get events
        response = product_invoice.get_invoice_events(
            invoice_id, 
            nfeio_config, 
            limit=int(limit), 
            starting_after=int(starting_after)
        )
        
        return {
            "success": True,
            "data": response
        }
        
    except product_invoice.NFeIOAPIError as e:
        frappe.log_error(
            f"NFe.io API Error: {str(e)}\n{frappe.get_traceback()}",
            "Query NFe Events API Error"
        )
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        frappe.log_error(
            f"Error querying NFe events: {str(e)}\n{frappe.get_traceback()}",
            "Query NFe Events Error"
        )
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def get_product_invoice_by_id(invoice_id):
    """
    API endpoint to get a product invoice (NFe) by ID
    
    Retrieves complete invoice details including status, items, taxes, and metadata.
    This is useful for checking invoice status, retrieving full details, or verifying data.
    
    Args:
        invoice_id: NFe.io invoice ID
        
    Returns:
        dict: Response with invoice data
        
    Example:
        frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.get_product_invoice_by_id",
            args: {
                invoice_id: "abc123"
            }
        })
    """
    from . import product_invoice
    
    try:
        # Validate input
        if not invoice_id:
            return {
                "success": False,
                "error": "Invoice ID is required"
            }
        
        # Get valid NFe.io configuration
        nfeio_config = _get_valid_nfeio_config()
        if not nfeio_config:
            return {
                "success": False,
                "error": "No valid NFe.io configuration found"
            }
        
        # Get invoice by ID
        response = product_invoice.get_product_invoice_by_id(invoice_id, nfeio_config)
        
        return {
            "success": True,
            "data": response
        }
        
    except product_invoice.NFeIOAPIError as e:
        frappe.log_error(
            f"NFe.io API Error: {str(e)}\n{frappe.get_traceback()}",
            "Get NFe By ID API Error"
        )
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        frappe.log_error(
            f"Unexpected error getting product invoice: {str(e)}\n{frappe.get_traceback()}",
            "Get NFe By ID Error"
        )
        return {
            "success": False,
            "error": f"Failed to get invoice: {str(e)}"
        }


@frappe.whitelist()
def get_product_invoice_pdf(invoice_id, force=False):
    """
    API endpoint to get PDF URL for invoice auxiliary document (DANFE)
    
    Returns the URL to download the DANFE (Documento Auxiliar da Nota Fiscal Eletrônica) PDF.
    
    Args:
        invoice_id: NFe.io invoice ID
        force: Force PDF generation regardless of FlowStatus (default: False)
        
    Returns:
        dict: Response with PDF URI
        
    Example:
        frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.get_product_invoice_pdf",
            args: {
                invoice_id: "abc123",
                force: true
            }
        })
    """
    from . import product_invoice
    
    try:
        # Validate input
        if not invoice_id:
            return {
                "success": False,
                "error": "Invoice ID is required"
            }
        
        # Get valid NFe.io configuration
        nfeio_config = _get_valid_nfeio_config()
        if not nfeio_config:
            return {
                "success": False,
                "error": "No valid NFe.io configuration found"
            }
        
        # Get PDF URL
        response = product_invoice.get_invoice_pdf(
            invoice_id, 
            nfeio_config, 
            force=bool(force)
        )
        
        return {
            "success": True,
            "data": response,
            "pdf_url": response.get("uri") if response else None
        }
        
    except product_invoice.NFeIOAPIError as e:
        frappe.log_error(
            f"NFe.io API Error: {str(e)}\n{frappe.get_traceback()}",
            "Get NFe PDF API Error"
        )
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        frappe.log_error(
            f"Error getting NFe PDF: {str(e)}\n{frappe.get_traceback()}",
            "Get NFe PDF Error"
        )
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def get_product_invoice_xml(invoice_id):
    """
    API endpoint to get XML URL for product invoice (NFe)
    
    Returns the URL to download the official NFe XML document.
    
    Args:
        invoice_id: NFe.io invoice ID
        
    Returns:
        dict: Response with XML URI
        
    Example:
        frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.get_product_invoice_xml",
            args: { invoice_id: "abc123" }
        })
    """
    from . import product_invoice
    
    try:
        # Validate input
        if not invoice_id:
            return {
                "success": False,
                "error": "Invoice ID is required"
            }
        
        # Get valid NFe.io configuration
        nfeio_config = _get_valid_nfeio_config()
        if not nfeio_config:
            return {
                "success": False,
                "error": "No valid NFe.io configuration found"
            }
        
        # Get XML URL
        response = product_invoice.get_invoice_xml(invoice_id, nfeio_config)
        
        return {
            "success": True,
            "data": response,
            "xml_url": response.get("uri") if response else None
        }
        
    except product_invoice.NFeIOAPIError as e:
        frappe.log_error(
            f"NFe.io API Error: {str(e)}\n{frappe.get_traceback()}",
            "Get NFe XML API Error"
        )
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        frappe.log_error(
            f"Error getting NFe XML: {str(e)}\n{frappe.get_traceback()}",
            "Get NFe XML Error"
        )
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def build_product_invoice_from_invoice(invoice_name):
    """
    API endpoint to build NFe.io payload from a Product Invoice document
    
    Converts a Frappe Product Invoice document to NFe.io API format.
    
    Args:
        invoice_name: Name of the Product Invoice document
        
    Returns:
        dict: Invoice data in NFe.io API format
        
    Example:
        frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.build_product_invoice_from_invoice",
            args: { invoice_name: "INV-001" }
        })
    """
    from . import product_invoice
    
    try:
        # Get invoice document
        invoice_doc = frappe.get_doc("Product Invoice", invoice_name)
        
        # Build payload
        payload = product_invoice.build_invoice_payload(invoice_doc)
        
        return {
            "success": True,
            "data": payload
        }
        
    except frappe.DoesNotExistError:
        return {
            "success": False,
            "error": f"Product Invoice '{invoice_name}' not found"
        }
    except Exception as e:
        frappe.log_error(
            f"Error building NFe payload: {str(e)}\n{frappe.get_traceback()}",
            "Build NFe Payload Error"
        )
        return {
            "success": False,
            "error": str(e)
        }
