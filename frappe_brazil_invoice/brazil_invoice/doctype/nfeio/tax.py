# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

"""
NFe.io Tax Calculation API Integration

This module handles tax calculations (ICMS, IPI, PIS, COFINS) using the NFe.io API.
API Documentation: https://nfe.io/docs/desenvolvedores/rest-api/calculo-de-impostos-v1/

Configuration:
- NFeIO doctype stores company_id, company_name, and api_token
"""

import frappe
from . import utils
import requests
from datetime import datetime


def _append_invoice_log(invoice_doc, log_type, message, details=None):
    """
    Append a formatted log entry to the invoice's process_events (logs)

    Args:
        invoice_doc: Invoice document instance
        log_type: Type of log (e.g., 'ERROR', 'WARNING', 'INFO', 'API_CALL')
        message: Main log message
        details: Optional additional details (dict or string)
    """
    if not hasattr(invoice_doc, "process_events"):
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build formatted log entry
    log_entry = f"[{timestamp}] [{log_type}] {message}"

    if details:
        if isinstance(details, dict):
            detail_lines = []
            for key, value in details.items():
                detail_lines.append(f"  • {key}: {value}")
            log_entry += "\n" + "\n".join(detail_lines)
        else:
            log_entry += f"\n  {details}"

    # Append to existing logs
    current_logs = invoice_doc.process_events or ""
    if current_logs:
        invoice_doc.process_events = current_logs + "\n\n" + log_entry
    else:
        invoice_doc.process_events = log_entry


def calculate(
        collection_id=None,
        issuer=None,
        recipient=None,
        operation_type=None,
        items=None,
        is_product_registration=None,
    ):
    """
    Calculate taxes using NFe.io Tax Calculation API

    Args:
        collection_id: Identificador da Coleção de Produtos (optional)
        issuer: Issuer information dict with taxRegime, taxProfile (optional), and state
        recipient: Recipient information dict with taxRegime, taxProfile (optional), and state
        operation_type: "Outgoing" (Saída) or "Incoming" (Entrada)
        items: List of item dicts with required fields (sku, ncm, quantity, unitAmount, origin, etc.)
        is_product_registration: Boolean indicating if this is for product registration (optional)

    API Reference:
        https://nfe.io/docs/desenvolvedores/rest-api/calculo-de-impostos-v1/calcula-os-impostos-de-uma-operacao/

    Returns:
        dict: API response with calculated tax values for each item
    """
    # Validate required parameters
    if not issuer:
        frappe.throw("Issuer information is required for tax calculation")
    if not recipient:
        frappe.throw("Recipient information is required for tax calculation")
    if not operation_type:
        frappe.throw("Operation type is required for tax calculation")
    if operation_type not in ["Outgoing", "Incoming"]:
        frappe.throw("Operation type must be either 'Outgoing' or 'Incoming'")
    if not items or not isinstance(items, list) or len(items) == 0: 
        frappe.throw("At least one item is required for tax calculation")

    try:
        # Fetch NFe.io configuration
        nfeio_config = utils.get_nfeio_config()

        # Build API payload
        payload = {
            "issuer": issuer,
            "recipient": recipient,
            "operationType": operation_type,
            "items": items,
        }

        # Add optional fields
        if collection_id is not None:
            payload["collectionId"] = collection_id
        if is_product_registration is not None:
            payload["isProductRegistration"] = is_product_registration

        # Call NFe.io Tax Calculation API
        api_url = f"https://nfe.io/tax-rules/{nfeio_config.company_id}/engine/calculate"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": nfeio_config.api_token,
        }

        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            params={"apikey": nfeio_config.api_token},
            timeout=30,
        )

        if response.status_code != 200:
            error_msg = f"NFe.io API returned status {response.status_code}: {response.text[:500]}"
            frappe.log_error(error_msg, "Tax Calculation API Error")
            frappe.throw(f"Tax calculation failed: {error_msg}")

        return response.json()

    except requests.exceptions.Timeout:
        error_msg = "NFe.io API request timed out after 30 seconds"
        frappe.log_error(error_msg, "Tax Calculation Timeout")
        frappe.throw(error_msg)
    except requests.exceptions.ConnectionError:
        error_msg = "Could not connect to NFe.io API"
        frappe.log_error(error_msg, "Tax Calculation Connection Error")
        frappe.throw(error_msg)
    except Exception as e:
        error_msg = f"Error calculating taxes with NFe.io: {str(e)}"
        frappe.log_error(
            f"{error_msg}\n{frappe.get_traceback()}",
            "Tax Calculation Error",
        )
        frappe.throw(f"Error calculating taxes: {str(e)}")


def calculate_taxes(invoice_doc):
    """
    Calculate taxes for an invoice document using NFe.io Tax Calculation API
    
    This is a wrapper function that prepares data from the invoice document
    and calls the calculate() API function.
    
    Args:
        invoice_doc: Invoice document instance
        use_fallback: Boolean to enable fallback (deprecated, will be removed)
    """
    if not invoice_doc.invoice_items_table:
        frappe.throw("Invoice has no items to calculate taxes.")

    try:
        # Fetch NFe.io configuration
        nfeio_config = utils.get_nfeio_config()

        # Fetch tax template
        tax_template_name = invoice_doc.tax_template
        if not tax_template_name:
            frappe.throw(f"Invoice '{invoice_doc.name}' does not have a Tax Template assigned")

        tax_template = frappe.get_doc("Tax", tax_template_name)

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
            items_for_calculation,
        )

        # Call NFe.io Tax Calculation API
        result = _call_nfeio_api(
            nfeio_config.api_token, nfeio_config.company_id, payload, invoice_doc
        )

        if result:
            # Update invoice with calculated tax values
            _update_invoice_with_tax_values(invoice_doc, tax_template, result)
            _append_invoice_log(
                invoice_doc,
                "INFO",
                "Tax calculation completed successfully",
                {
                    "Source": "NFe.io API",
                    "Company ID": nfeio_config.company_id,
                    "Items Calculated": len(result.get("items", [])),
                },
            )
        else:
            # API call failed
            error_msg = "NFe.io API call failed. No tax values calculated."
            _append_invoice_log(
                invoice_doc,
                "ERROR",
                error_msg,
                {
                    "API Endpoint": f"https://nfe.io/tax-rules/{nfeio_config.company_id}/engine/calculate",
                    "Status": "Failed",
                },
            )
            frappe.throw(error_msg)

    except Exception as e:
        error_msg = f"Error calculating taxes with NFe.io: {str(e)}"
        _append_invoice_log(
            invoice_doc,
            "ERROR",
            "Tax calculation error",
            {
                "Error Type": type(e).__name__,
                "Error Message": str(e),
            },
        )
        frappe.log_error(
            f"{error_msg}\n{frappe.get_traceback()}",
            "Tax Calculation Error",
        )
        frappe.throw(f"Error calculating taxes: {str(e)}")

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
            "valorTotal": float(item.amount or 0),
        }
        items_for_calculation.append(item_data)

    return items_for_calculation


def _build_api_payload(
    invoice_doc, tax_template, company_state, destination_state, items
):
    """Build the payload for NFe.io API request

    New API format as per: https://nfe.io/docs/desenvolvedores/rest-api/calculo-de-impostos-v1/calcula-os-impostos-de-uma-operacao/
    """
    # Transform items to new format
    api_items = []
    for item in items:
        api_item = {
            "sku": item.get("codigo", ""),
            "ncm": item.get("ncm", ""),
            "quantity": item.get("quantidade", 1),
            "unitAmount": item.get("valorUnitario", 0),
            "origin": "National",  # Default origin
        }

        # Add optional values if present
        if invoice_doc.total_freight and tax_template.add_freight_icms:
            api_item["freightAmount"] = float(invoice_doc.total_freight or 0) / len(
                items
            )
        if invoice_doc.total_insurance and tax_template.add_insurance_icms:
            api_item["insuranceAmount"] = float(invoice_doc.total_insurance or 0) / len(
                items
            )
        if invoice_doc.other_expenses and tax_template.add_other_expenses_icms:
            api_item["othersAmount"] = float(invoice_doc.other_expenses or 0) / len(
                items
            )

        api_items.append(api_item)

    # Determine tax regime (simplified, may need adjustment based on company config)
    tax_regime = "NationalSimple"  # Can be: NationalSimple, RealProfit, PresumedProfit

    payload = {
        "issuer": {
            "taxRegime": tax_regime,
            "state": company_state,
        },
        "recipient": {
            "taxRegime": tax_regime,
            "state": destination_state,
        },
        "operationType": "Outgoing",  # Saída
        "items": api_items,
        "isProductRegistration": False,
    }

    return payload


def _call_nfeio_api(api_key, company_id, payload, invoice_doc=None):
    """Make the API call to NFe.io tax calculation endpoint

    API Reference: https://nfe.io/docs/desenvolvedores/rest-api/calculo-de-impostos-v1/calcula-os-impostos-de-uma-operacao/
    Endpoint: POST /tax-rules/:tenantId/engine/calculate
    """
    api_url = f"https://nfe.io/tax-rules/{company_id}/engine/calculate"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": api_key,
    }

    response = requests.post(
        api_url,
        json=payload,
        headers=headers,
        params={"apikey": api_key},
        timeout=30,
    )

    if response.status_code == 200:
        return response.json()
    else:
        # Truncate response text if too long (for logs)
        response_text = response.text
        if len(response_text) > 500:
            response_text = response_text[:500] + "... (truncated)"

        error_msg = (
            f"NFe.io API returned status {response.status_code}: {response_text}"
        )

        # Log to invoice if provided
        if invoice_doc:
            _append_invoice_log(
                invoice_doc,
                "ERROR",
                "NFe.io API Request Failed",
                {
                    "HTTP Status": response.status_code,
                    "API Endpoint": api_url,
                    "Company ID": company_id,
                    "Response": response_text,
                    "Items in Request": len(payload.get("items", [])),
                },
            )

        print(f"\n🔴 NFe.io API Error: {error_msg}\n")  # Debug print
        frappe.log_error(error_msg, "Tax Calculation API Error")
        return None


def _update_invoice_with_tax_values(invoice_doc, tax_template, result):
    """Update invoice document with calculated tax values from API response

    The new API returns an array of items with calculated taxes.
    We sum up the values from all items to get the invoice totals.
    """
    items_result = result.get("items", [])

    if not items_result:
        return

    # Sum up tax values from all items
    icms_total = 0
    ipi_total = 0
    pis_total = 0
    cofins_total = 0

    for item in items_result:
        # ICMS values
        if tax_template.calculate_automatically_icms:
            icms_data = item.get("icms", {})
            icms_value = icms_data.get("vICMS")
            if icms_value:
                icms_total += float(icms_value)

        # IPI values
        if tax_template.calculate_automatically_ipi:
            ipi_data = item.get("ipi", {})
            ipi_value = ipi_data.get("vIPI")
            if ipi_value:
                ipi_total += float(ipi_value)

        # PIS values
        if tax_template.calculate_automatically_pis:
            pis_data = item.get("pis", {})
            pis_value = pis_data.get("vPIS")
            if pis_value:
                pis_total += float(pis_value)

        # COFINS values
        if tax_template.calculate_automatically_cofins:
            cofins_data = item.get("cofins", {})
            cofins_value = cofins_data.get("vCOFINS")
            if cofins_value:
                cofins_total += float(cofins_value)

    # Update invoice with totals
    if tax_template.calculate_automatically_icms and hasattr(invoice_doc, "icms_value"):
        invoice_doc.icms_value = icms_total

    if tax_template.calculate_automatically_ipi and hasattr(invoice_doc, "ipi_value"):
        invoice_doc.ipi_value = ipi_total

    if tax_template.calculate_automatically_pis and hasattr(invoice_doc, "pis_value"):
        invoice_doc.pis_value = pis_total

    if tax_template.calculate_automatically_cofins and hasattr(
        invoice_doc, "cofins_value"
    ):
        invoice_doc.cofins_value = cofins_total


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

    if hasattr(invoice_doc, "icms_value"):
        invoice_doc.icms_value = icms_value


def _calculate_ipi_fallback(invoice_doc, tax_template):
    """Calculate IPI using hardcoded NCM rates as fallback"""
    ipi_rates = {
        "85044090": 9.75,
        "8504.40.90": 9.75,
        "85049090": 6.50,
        "8504.90.90": 6.50,
        "85437099": 6.50,
        "8543.70.99": 6.50,
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

    if hasattr(invoice_doc, "ipi_value"):
        invoice_doc.ipi_value = ipi_value
