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
        invoice_doc = frappe.get_doc("Invoices", invoice_name)
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
