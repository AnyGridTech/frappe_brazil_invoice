# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

import frappe
from . import utils
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

# ============================================================================
# Product Invoice Operations - Whitelisted API Endpoints
# ============================================================================

@frappe.whitelist()
def calculate_product_invoice_taxes(issuer, recipient, operation_type, items, collection_id=None, is_product_registration=None):
    """
    API endpoint to calculate taxes using NFe.io Tax Calculation API

    Args:
        issuer: Issuer information dict with taxRegime, taxProfile (optional), and state
        recipient: Recipient information dict with taxRegime, taxProfile (optional), and state  
        operation_type: "Outgoing" (Saída) or "Incoming" (Entrada)
        items: List of item dicts with required fields (sku, ncm, quantity, unitAmount, origin, etc.)
        collection_id: Identificador da Coleção de Produtos (optional)
        is_product_registration: Boolean indicating if this is for product registration (optional)

    Returns:
        dict: Items with calculated tax values
    """
    try:
        # Calculate taxes
        data = tax.calculate(
            collection_id=collection_id,
            issuer=issuer,
            recipient=recipient,
            operation_type=operation_type,
            items=items,
            is_product_registration=is_product_registration
        )

        # Return calculated values
        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        frappe.log_error(
            f"Error calculating taxes: {str(e)}\n{frappe.get_traceback()}",
            "Tax Calculation API Error",
        )
        return {
            "success": False,
            "error": str(e),
        }

@frappe.whitelist()
def issue_product_invoice(invoice_data, is_test_invoice=0):
    """
    API endpoint to issue/emit a product invoice (NFe) via NFe.io
    
    This queues the invoice for asynchronous processing. The response indicates
    successful queuing, not successful emission. Use webhooks or query_product_invoice_events
    to track the actual emission status.
    
    Args:
        invoice_data: JSON string or dict with invoice data in NFe.io format
        is_test_invoice: Flag to indicate if this is a test invoice (0 or 1)
        
    Returns:
        dict: Response with success status and invoice details
        
    Example:
        frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.issue_product_invoice",
            args: { invoice_data: {...}, is_test_invoice: 1 }
        })
    """
    from . import product_invoice
    
    try:
        # Parse invoice data if it's a JSON string
        if isinstance(invoice_data, str):
            import json
            invoice_data = json.loads(invoice_data)
        
        # Convert is_test_invoice to int if needed
        if isinstance(is_test_invoice, str):
            is_test_invoice = 1 if is_test_invoice in ["1", "true", "True"] else 0
        else:
            is_test_invoice = int(is_test_invoice or 0)
        
        # Get valid NFe.io configuration based on is_test_invoice flag
        nfeio_config = utils.get_nfeio_config(is_test_config=is_test_invoice)
        if not nfeio_config:
            return {
                "success": False,
                "error": f"No valid NFe.io configuration found (with is_test_config={is_test_invoice}). Please create an NFeIO document with API credentials."
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
        nfeio_config = utils.get_nfeio_config()
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
def get_product_invoice_by_id(invoice_id, is_test_invoice=0):
    """
    API endpoint to get a product invoice (NFe) by ID
    
    Args:
        invoice_id: NFe.io invoice ID
        is_test_invoice: Flag to indicate if this is a test invoice (0 or 1)
        
    Returns:
        dict: Complete invoice data
    """
    from . import product_invoice
    
    try:
        # Validate input
        if not invoice_id:
            return {
                "success": False,
                "error": "Invoice ID is required"
            }
        
        # Convert is_test_invoice to int if needed
        if isinstance(is_test_invoice, str):
            is_test_invoice = 1 if is_test_invoice in ["1", "true", "True"] else 0
        else:
            is_test_invoice = int(is_test_invoice or 0)
        
        # Get valid NFe.io configuration based on is_test_invoice flag
        nfeio_config = utils.get_nfeio_config(is_test_config=is_test_invoice)
        if not nfeio_config:
            return {
                "success": False,
                "error": f"No valid NFe.io configuration found (with is_test_config={is_test_invoice})"
            }
        
        print(f"\n🔍 get_product_invoice_by_id using config: {nfeio_config.name}")
        print(f"   Company ID: {nfeio_config.company_id}")
        print(f"   is_test_config: {nfeio_config.is_test_config}")
        
        # Get invoice
        response = product_invoice.get_product_invoice_by_id(invoice_id, nfeio_config)
        
        return {
            "success": True,
            "data": response
        }
        
    except product_invoice.NFeIOAPIError as e:
        frappe.log_error(
            f"NFe.io API Error: {str(e)}\n{frappe.get_traceback()}",
            "Get NFe API Error"
        )
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        frappe.log_error(
            f"Error getting NFe: {str(e)}\n{frappe.get_traceback()}",
            "Get NFe Error"
        )
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def query_product_invoice_events(invoice_id, limit=10, starting_after=0, is_test_invoice=0):
    """
    API endpoint to query events for a product invoice (NFe)
    
    Retrieves the event history for tracking invoice processing status.
    Events include emission, cancellation, authorization, rejection, etc.
    
    Args:
        invoice_id: NFe.io invoice ID
        limit: Maximum number of events to retrieve (default: 10)
        starting_after: Pagination starting index (default: 0)
        is_test_invoice: Flag to indicate if this is a test invoice (0 or 1)
        
    Returns:
        dict: Response with events array and pagination info
        
    Example:
        frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.query_product_invoice_events",
            args: {
                invoice_id: "abc123",
                limit: 20,
                is_test_invoice: 1
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
        
        # Convert is_test_invoice to int if needed
        if isinstance(is_test_invoice, str):
            is_test_invoice = 1 if is_test_invoice in ["1", "true", "True"] else 0
        else:
            is_test_invoice = int(is_test_invoice or 0)
        
        # Get valid NFe.io configuration based on is_test_invoice flag
        nfeio_config = utils.get_nfeio_config(is_test_config=is_test_invoice)
        if not nfeio_config:
            return {
                "success": False,
                "error": f"No valid NFe.io configuration found (with is_test_config={is_test_invoice})"
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
def get_product_invoice_pdf(invoice_id, force=False, is_test_invoice=0):
    """
    API endpoint to get PDF URL for invoice auxiliary document (DANFE)
    
    Returns the URL to download the DANFE (Documento Auxiliar da Nota Fiscal Eletrônica) PDF.
    
    Includes automatic retry logic: 3 retries with 3 seconds delay between attempts.
    
    Args:
        invoice_id: NFe.io invoice ID
        force: Force PDF generation regardless of FlowStatus (default: False)
        is_test_invoice: Flag to select test (1) or production (0) config (default: 0)
        
    Returns:
        dict: Response with PDF URI
        
    Example:
        frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.get_product_invoice_pdf",
            args: {
                invoice_id: "abc123",
                force: true,
                is_test_invoice: 1
            }
        })
    """
    from . import product_invoice
    import time
    
    max_retries = 3
    retry_delay = 3  # seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            # Validate input
            if not invoice_id:
                return {
                    "success": False,
                    "error": "Invoice ID is required"
                }
            
            # Get valid NFe.io configuration
            is_test_invoice = int(is_test_invoice)  # Ensure it's an integer
            nfeio_config = utils.get_nfeio_config(is_test_config=is_test_invoice)
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
            if attempt < max_retries:
                frappe.logger().warning(
                    f"NFe.io API error getting PDF on attempt {attempt}/{max_retries}: {str(e)}. Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
            else:
                frappe.log_error(
                    f"NFe.io API Error after {max_retries} attempts: {str(e)}\n{frappe.get_traceback()}",
                    "Get NFe PDF API Error"
                )
                return {
                    "success": False,
                    "error": str(e)
                }
        except Exception as e:
            if attempt < max_retries:
                frappe.logger().warning(
                    f"Unexpected error getting PDF on attempt {attempt}/{max_retries}: {str(e)}. Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
            else:
                frappe.log_error(
                    f"Unexpected error after {max_retries} attempts: {str(e)}\n{frappe.get_traceback()}",
                    "Get NFe PDF Error"
                )
                return {
                    "success": False,
                    "error": f"Failed to get PDF: {str(e)}"
                }

@frappe.whitelist()
def get_product_invoice_xml(invoice_id, is_test_invoice=0):
    """
    API endpoint to get XML URL for product invoice (NFe)
    
    Returns the URL to download the official NFe XML document.
    
    Includes automatic retry logic: 3 retries with 3 seconds delay between attempts.
    
    Args:
        invoice_id: NFe.io invoice ID
        is_test_invoice: Flag to select test (1) or production (0) config (default: 0)
        
    Returns:
        dict: Response with XML URI
        
    Example:
        frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.get_product_invoice_xml",
            args: { invoice_id: "abc123" }
        })
    """
    from . import product_invoice
    import time
    
    max_retries = 3
    retry_delay = 3  # seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            # Validate input
            if not invoice_id:
                return {
                    "success": False,
                    "error": "Invoice ID is required"
                }
            
            # Get valid NFe.io configuration
            is_test_invoice = int(is_test_invoice)  # Ensure it's an integer
            nfeio_config = utils.get_nfeio_config(is_test_config=is_test_invoice)
            if not nfeio_config:
                return {
                    "success": False,
                    "error": "No valid NFe.io configuration found"
                }
            
            # Get XML URL
            response = product_invoice.get_invoice_xml(invoice_id, nfeio_config)
            
            return {
                "success": True,
                "xml_url": response.get("uri") if response else None
            }
            
        except product_invoice.NFeIOAPIError as e:
            if attempt < max_retries:
                frappe.logger().warning(
                    f"NFe.io API error getting XML on attempt {attempt}/{max_retries}: {str(e)}. Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
            else:
                frappe.log_error(
                    f"NFe.io API Error after {max_retries} attempts: {str(e)}\n{frappe.get_traceback()}",
                    "Get NFe XML API Error"
                )
                return {
                    "success": False,
                    "error": str(e)
                }
        except Exception as e:
            if attempt < max_retries:
                frappe.logger().warning(
                    f"Unexpected error getting XML on attempt {attempt}/{max_retries}: {str(e)}. Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
            else:
                frappe.log_error(
                    f"Error getting NFe XML after {max_retries} attempts: {str(e)}\n{frappe.get_traceback()}",
                    "Get NFe XML Error"
                )
                return {
                    "success": False,
                    "error": str(e)
                }