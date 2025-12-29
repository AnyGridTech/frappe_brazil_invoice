# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
import json
from datetime import datetime
from ..nfeio import tax as nfeio_tax


def validate_cpf(cpf):
    """
    Validate Brazilian CPF (Cadastro de Pessoas Físicas)
    
    Args:
        cpf: CPF string (can contain dots and hyphens)
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Remove non-digit characters
    cpf = ''.join(filter(str.isdigit, str(cpf)))
    
    # CPF must have exactly 11 digits
    if len(cpf) != 11:
        return False
    
    # Check if all digits are the same (invalid CPFs like 111.111.111-11)
    if cpf == cpf[0] * 11:
        return False
    
    # Calculate first check digit
    sum_digits = sum(int(cpf[i]) * (10 - i) for i in range(9))
    first_digit = (sum_digits * 10 % 11) % 10
    
    if int(cpf[9]) != first_digit:
        return False
    
    # Calculate second check digit
    sum_digits = sum(int(cpf[i]) * (11 - i) for i in range(10))
    second_digit = (sum_digits * 10 % 11) % 10
    
    if int(cpf[10]) != second_digit:
        return False
    
    return True


def validate_cnpj(cnpj):
    """
    Validate Brazilian CNPJ (Cadastro Nacional da Pessoa Jurídica)
    
    Args:
        cnpj: CNPJ string (can contain dots, slashes, and hyphens)
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Remove non-digit characters
    cnpj = ''.join(filter(str.isdigit, str(cnpj)))
    
    # CNPJ must have exactly 14 digits
    if len(cnpj) != 14:
        return False
    
    # Check if all digits are the same (invalid CNPJs)
    if cnpj == cnpj[0] * 14:
        return False
    
    # Calculate first check digit
    weights_first = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum_digits = sum(int(cnpj[i]) * weights_first[i] for i in range(12))
    first_digit = 0 if sum_digits % 11 < 2 else 11 - (sum_digits % 11)
    
    if int(cnpj[12]) != first_digit:
        return False
    
    # Calculate second check digit
    weights_second = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum_digits = sum(int(cnpj[i]) * weights_second[i] for i in range(13))
    second_digit = 0 if sum_digits % 11 < 2 else 11 - (sum_digits % 11)
    
    if int(cnpj[13]) != second_digit:
        return False
    
    return True


class ProductInvoice(Document):
    def _handle_processing_error(self, error_type, error_message):
        """
        Handle errors that occur during Processing status by changing status to Processing Error
        and logging the error details.

        Args:
            error_type: Type of error (e.g., 'Tax Calculation Error', 'API Error')
            error_message: Detailed error message
        """
        # Change status to Processing Error
        self.invoice_status = "Processing Error"

        # Log the error using the standard logging format
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [ERROR] {error_type}\n  {error_message}"

        # Append to errors_field
        if self.errors_field:
            self.errors_field = self.errors_field + "\n\n" + log_entry
        else:
            self.errors_field = log_entry

    def _handle_tax_calculation_error(self, error_type, error_message):
        """
        Handle errors that occur during tax calculation at Draft/Non Processed status
        by changing status to Tax Calculation Error and logging the error details.

        Args:
            error_type: Type of error (e.g., 'API Error', 'Configuration Error')
            error_message: Detailed error message
        """
        # Change status to Tax Calculation Error
        self.invoice_status = "Tax Calculation Error"

        # Log the error using the standard logging format
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [ERROR] {error_type}\n  {error_message}"

        # Append to errors_field
        if self.errors_field:
            self.errors_field = self.errors_field + "\n\n" + log_entry
        else:
            self.errors_field = log_entry

    def validate_client_id_number(self):
        """Validate CPF or CNPJ format based on client_type
        
        For Individual (Pessoa Física): Validates CPF (11 digits)
        For Company (Pessoa Jurídica): Validates CNPJ (14 digits)
        """
        if not self.client_id_number:
            return  # Field might not be mandatory in all cases
        
        # Remove non-digit characters for length check
        clean_id = ''.join(filter(str.isdigit, str(self.client_id_number)))
        
        # Determine expected type based on client_type or number length
        if self.client_type == "Individual":
            # Expect CPF
            if not validate_cpf(self.client_id_number):
                frappe.throw(
                    _("Invalid CPF format. Please provide a valid CPF number for Individual client type."),
                    frappe.ValidationError
                )
        elif self.client_type == "Company":
            # Expect CNPJ
            if not validate_cnpj(self.client_id_number):
                frappe.throw(
                    _("Invalid CNPJ format. Please provide a valid CNPJ number for Company client type."),
                    frappe.ValidationError
                )
        else:
            # If client_type is not set, infer from number length
            if len(clean_id) == 11:
                if not validate_cpf(self.client_id_number):
                    frappe.throw(
                        _("Invalid CPF format. The provided number appears to be a CPF (11 digits) but is invalid."),
                        frappe.ValidationError
                    )
            elif len(clean_id) == 14:
                if not validate_cnpj(self.client_id_number):
                    frappe.throw(
                        _("Invalid CNPJ format. The provided number appears to be a CNPJ (14 digits) but is invalid."),
                        frappe.ValidationError
                    )
            else:
                frappe.throw(
                    _("Invalid ID number format. Expected CPF (11 digits) or CNPJ (14 digits), got {0} digits.").format(len(clean_id)),
                    frappe.ValidationError
                )

    def before_save(self):
        """Actions before saving the document

        Validation errors at Non Processed should just raise - they should NOT
        auto-transition to Processing Error. Processing Error is only for errors
        that occur during API processing (when status is Processing).
        """
        try:
            # Set operation_type from tax template if tax_template is selected
            self.set_operation_type_from_template()
            # Calculate taxes from template or automatically
            self.calculate_taxes_from_template()
            # Calculate total and product fields
            self.calculate_total()
        except Exception as e:
            # If we're in Processing status, catch the error and transition to Processing Error
            # This is the ONLY case where auto-transition to Processing Error should happen
            if self.invoice_status == "Processing" and getattr(self.flags, "ignore_processing_lock", False):
                error_type = type(e).__name__
                error_msg = str(e)
                self._handle_processing_error(
                    f"Processing Failed: {error_type}", error_msg
                )
                # Don't re-raise - allow the save to continue with Processing Error status
            else:
                # For all other cases (including Non Processed), re-raise the exception
                # Users will see the validation error and must fix it
                raise

    def validate(self):
        """Ensure invoice has items and prevent status changes without items"""
        # Process invoice items to auto-fill from serial numbers
        self.process_invoice_items()

        # Block user modifications when invoice is in Processing status
        self.validate_processing_lock()

        # Validate workflow transitions follow business rules
        self.validate_workflow_transitions()

        # Lock invoice_items_table changes at Processing status and forward
        self.validate_items_lock()

        # Validate responsible field is mandatory for Created status and beyond
        self.validate_responsible()

        # Validate CPF/CNPJ format
        self.validate_client_id_number()

        # Validate Invoice ID is mandatory when transitioning to Processing
        self.validate_invoice_id()

        # Validate tax fields are calculated before Processing
        self.validate_tax_calculation()

        # Validate return invoice reference fields
        self.validate_return_invoice_fields()

        # Validate invoice access key field
        self.validate_invoice_access_key()

        # Validate required fields when transitioning to Issued
        self.validate_issued_status_fields()

        # Must have at least one item row
        if not self.invoice_items_table or len(self.invoice_items_table) == 0:
            frappe.throw(
                _("Invoice must include at least one item (invoice_items_table).")
            )

        # Guard status changes that require items
        restricted_statuses = {"Non Processed", "Processing", "Issued"}
        if getattr(self, "invoice_status", None) in restricted_statuses:
            # Redundant due to above, but explicit for clarity
            if not self.invoice_items_table or len(self.invoice_items_table) == 0:
                frappe.throw(
                    _("Cannot set status to {0} without invoice items").format(
                        self.invoice_status
                    )
                )

        # Calculate taxes automatically if in Draft or Created status
        if self.invoice_status in [None, "Draft", "Non Processed"]:
            self.calculate_automatic_taxes()

    def process_invoice_items(self):
        """Process invoice items to auto-fill fields

        Two-stage auto-fill strategy:
        1. If serial_number is provided → auto-fill item_code
        2. If item_code is provided → auto-fill all other fields

        This allows both use cases:
        - Serial number provided: serial_number → item_code → other fields
        - Item code provided directly: item_code → other fields
        """
        for item in self.invoice_items_table:
            # Stage 1: Auto-fill item_code from serial_number
            if hasattr(item, "serial_number") and item.serial_number:
                # Enforce quantity = 1 for serial numbers
                if item.quantity and item.quantity != 1:
                    frappe.throw(
                        _(
                            "Quantity must be 1 when Serial Number is provided. Serial numbers are unique and cannot have multiple quantities."
                        )
                    )
                item.quantity = 1

                # Auto-fill item_code from serial number if not already set
                if not item.item_code:
                    serial_doc = frappe.get_doc("Serial No", item.serial_number)
                    item.item_code = serial_doc.item_code

            # Stage 2: Auto-fill other fields from item_code (works for both cases)
            if item.item_code:
                item_doc = frappe.get_doc("Item", item.item_code)

                # Auto-fill item details
                if not item.item_name:
                    item.item_name = item_doc.item_name
                if not item.rate:
                    item.rate = item_doc.valuation_rate or item_doc.standard_rate
                if not item.ncm:
                    item.ncm = item_doc.get("ncm")
                if not item.description:
                    item.description = item_doc.description or item_doc.item_name

            # Calculate amount if rate and quantity are available
            if item.rate and item.quantity:
                item.amount = item.rate * item.quantity

    def validate_items_lock(self):
        """Prevent changes to invoice_items_table at Processing status and forward"""
        if not self.is_new():
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.invoice_status in [
                "Processing",
                "Issued",
                "Rejected",
                "Contingency",
                "Unused",
            ]:
                # Compare invoice items
                old_items = {
                    item.name: item for item in (old_doc.invoice_items_table or [])
                }
                new_items = {
                    item.name: item for item in (self.invoice_items_table or [])
                }

                # Check if items were added or removed
                if set(old_items.keys()) != set(new_items.keys()):
                    frappe.throw(
                        _(
                            "Cannot add or remove items when invoice status is {0}"
                        ).format(old_doc.invoice_status)
                    )

                # Check if any item was modified
                for item_name, old_item in old_items.items():
                    new_item = new_items.get(item_name)
                    if new_item:
                        # Check key fields for changes
                        fields_to_check = [
                            "item_code",
                            "quantity",
                            "rate",
                            "amount",
                            "ncm",
                            "serial_no",
                        ]
                        for field in fields_to_check:
                            if getattr(old_item, field, None) != getattr(
                                new_item, field, None
                            ):
                                frappe.throw(
                                    _(
                                        "Cannot modify invoice items when invoice status is {0}"
                                    ).format(old_doc.invoice_status)
                                )

    def validate_processing_lock(self):
        """Validate that users cannot modify invoices in Processing status
        
        When an invoice is in Processing status, it has been sent to external API
        for processing. To prevent false positives and data inconsistencies, users
        are blocked from making any modifications to the invoice.
        
        Backend/API can bypass this restriction by setting:
        invoice.flags.ignore_processing_lock = True
        """
        if not self.is_new():
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.invoice_status == "Processing":
                # Check if backend/API is making the change
                if not getattr(self.flags, "ignore_processing_lock", False):
                    # This is a user modification - check if anything changed
                    # Exclude standard meta fields, child tables, workflow status, and Sefaz event fields
                    exclude_fields = ['modified', 'modified_by', 'idx', 'docstatus', 
                                    'invoice_items_table', '_comments', '_assign', '_liked_by',
                                    'invoice_status',  # Allow status transitions
                                    # Allow Sefaz event fields (set during workflow transitions)
                                    'invoice_ref_series', 'invoice_ref_number', 'invoice_ref_access_key',
                                    'invoice_serie', 'invoice_number', 'invoice_link', 'invoice_access_key',
                                    'errors_field']  # Allow error logging
                    
                    for field in self.meta.get_valid_columns():
                        if field in exclude_fields:
                            continue
                        
                        old_value = getattr(old_doc, field, None)
                        new_value = getattr(self, field, None)
                        
                        if old_value != new_value:
                            frappe.throw(
                                _(
                                    "Cannot modify invoice in Processing status. "
                                    "The invoice has been sent to the external API and "
                                    "is currently being processed. Please wait for the "
                                    "processing to complete."
                                ),
                                frappe.PermissionError
                            )

    def validate_workflow_transitions(self):
        """Validate that workflow transitions follow business rules
        
        Key rule: Processing Error status can only be reached from Processing status.
        This prevents validation errors at Non Processed from incorrectly moving to
        Processing Error (which should only happen during API processing failures).
        """
        if not self.is_new():
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.invoice_status != self.invoice_status:
                # Status is changing - validate transitions
                
                # Processing Error can only come from Processing
                if self.invoice_status == "Processing Error":
                    if old_doc.invoice_status != "Processing":
                        frappe.throw(
                            _(
                                "Processing Error status can only be reached from Processing status. "
                                "Current status is '{0}'. If you encountered a validation error, "
                                "please fix the issue and try again."
                            ).format(old_doc.invoice_status)
                        )

    def validate_responsible(self):
        """Validate that Responsible field is mandatory for Created status and beyond

        The Responsible field (delivery_supervisor) must be filled when invoice
        reaches Created status and must never be empty afterwards.
        """
        statuses_requiring_responsible = [
            "Non Processed",
            "Processing",
            "Issued",
            "Rejected",
            "Contingency",
            "Unused",
        ]

        if self.invoice_status in statuses_requiring_responsible:
            if not self.delivery_supervisor or not self.delivery_supervisor.strip():
                frappe.throw(
                    _(
                        "Responsible field is mandatory for invoice status '{0}'. Please specify who is responsible for this invoice."
                    ).format(self.invoice_status)
                )

    def validate_invoice_id(self):
        """Validate that Invoice ID is mandatory when transitioning to Processing status

        When an invoice moves from Created to Processing and onwards status, the Invoice ID
        field must be filled.
        """
        statuses_requiring_invoice_id = [
            "Processing",
            "Issued",
            "Rejected",
            "Contingency",
            "Unused",
        ]
        if self.invoice_status in statuses_requiring_invoice_id:
            if not self.invoice_id or not self.invoice_id.strip():
                frappe.throw(
                    _("Invoice ID is mandatory. Please provide the Invoice ID.")
                )

    def validate_tax_calculation(self):
        """Validate that tax fields are calculated before transitioning to Processing status

        When an invoice moves to Processing status, it must have tax values calculated.
        This validates that if the tax template requires automatic calculation for any tax,
        the corresponding tax value field must be filled (non-zero or explicitly zero after calculation).
        """
        if self.invoice_status == "Processing" and self.tax_template:
            try:
                tax_template = frappe.get_doc("Tax", self.tax_template)

                # Check which taxes require calculation
                taxes_to_check = []

                if tax_template.calculate_automatically_icms:
                    # ICMS should be calculated - check if value exists
                    if not hasattr(self, "icms_value"):
                        taxes_to_check.append("ICMS")
                    # Value can be zero if calculated as zero, but must be set (not None)
                    elif self.icms_value is None:
                        taxes_to_check.append("ICMS")

                if tax_template.calculate_automatically_ipi:
                    if not hasattr(self, "ipi_value"):
                        taxes_to_check.append("IPI")
                    elif self.ipi_value is None:
                        taxes_to_check.append("IPI")

                if tax_template.calculate_automatically_pis:
                    if not hasattr(self, "pis_value"):
                        taxes_to_check.append("PIS")
                    elif self.pis_value is None:
                        taxes_to_check.append("PIS")

                if tax_template.calculate_automatically_cofins:
                    if not hasattr(self, "cofins_value"):
                        taxes_to_check.append("COFINS")
                    elif self.cofins_value is None:
                        taxes_to_check.append("COFINS")

                if taxes_to_check:
                    frappe.throw(
                        _(
                            "Tax calculation is required before moving to Processing status. "
                            "The following taxes need to be calculated: {0}. "
                            "Please ensure the tax template calculations are completed."
                        ).format(", ".join(taxes_to_check))
                    )
            except Exception as e:
                # If tax template doesn't exist or other error, skip validation
                if "does not exist" not in str(e):
                    frappe.log_error(
                        f"Error validating tax calculation: {str(e)}",
                        "Tax Validation Error",
                    )

    def validate_return_invoice_fields(self):
        """Validate that reference fields are filled when is_return_invoice is checked

        When is_return_invoice is checked, the following fields become mandatory:
        - invoice_ref_series
        - invoice_ref_number
        - invoice_ref_access_key
        """
        if self.is_return_invoice:
            required_fields = [
                ("invoice_ref_series", "Invoice Ref. Series"),
                ("invoice_ref_number", "Invoice Ref. Number"),
                ("invoice_ref_access_key", "Invoice Ref. Access Key"),
            ]

            missing_fields = []
            for field_name, field_label in required_fields:
                field_value = getattr(self, field_name, None)
                if not field_value or (
                    isinstance(field_value, str) and not field_value.strip()
                ):
                    missing_fields.append(field_label)

            if missing_fields:
                frappe.throw(
                    _(
                        "The following fields are mandatory when 'Is Return Invoice' is checked: {0}"
                    ).format(", ".join(missing_fields))
                )

    def validate_invoice_access_key(self):
        """Validate invoice_access_key field based on status

        The invoice_access_key field should be filled when invoice reaches certain statuses.
        Similar behavior to other Sefaz Events fields like invoice_id, invoice_serie, etc.
        """
        # Invoice Access Key is typically filled during Processing or Issued status
        # It should be present when invoice_id exists (meaning it's been sent to Sefaz)
        if self.invoice_status in [
            "Processing",
            "Issued",
            "Rejected",
            "Contingency",
        ]:
            if self.invoice_id and not self.invoice_access_key:
                # This is a warning rather than blocking validation
                # since access key might be generated asynchronously
                pass

    def validate_issued_status_fields(self):
        """Validate that required fields are filled when transitioning to Issued status

        When an invoice moves from Processing to Issued status, the following fields
        must be filled: Invoice Ref. Series, Invoice Ref. Number, Invoice Ref. Access Key,
        Invoice Serie, Invoice Number, and Invoice Link.
        """
        if self.invoice_status == "Issued":
            required_fields = [
                ("invoice_ref_series", "Invoice Ref. Series"),
                ("invoice_ref_number", "Invoice Ref. Number"),
                ("invoice_ref_access_key", "Invoice Ref. Access Key"),
                ("invoice_serie", "Invoice Serie"),
                ("invoice_number", "Invoice Number"),
                ("invoice_link", "Invoice Link"),
            ]

            missing_fields = []
            for field_name, field_label in required_fields:
                field_value = getattr(self, field_name, None)
                if not field_value or (
                    isinstance(field_value, str) and not field_value.strip()
                ):
                    missing_fields.append(field_label)

            if missing_fields:
                frappe.throw(
                    _(
                        "The following fields are mandatory when moving to Issued status: {0}"
                    ).format(", ".join(missing_fields))
                )

    def set_operation_type_from_template(self):
        """Set operation_type automatically from tax template

        When a tax_template is selected, fetch its operation_type and set it
        on the invoice. This makes operation_type read-only when template is selected.
        """
        if self.tax_template:
            try:
                tax_doc = frappe.get_doc("Tax", self.tax_template)
                if tax_doc.get("operation_type"):
                    self.operation_type = tax_doc.operation_type
            except Exception:
                # If tax template doesn't exist or has no operation_type, continue
                pass

    def calculate_total(self):
        """Calculate invoice total and product summary automatically

        Calculates:
        - product_quantity: Total quantity of all items
        - product_gross_weight: Total gross weight (from item master * quantity)
        - product_net_weight: Total net weight (from item master * quantity)
        - total: sum(items.amount) + freight + insurance + other_expenses - discount
        """
        from frappe.utils import flt

        # Calculate product quantity (sum of all item quantities)
        self.product_quantity = str(
            sum(int(item.quantity or 0) for item in (self.invoice_items_table or []))
        )

        # Calculate product weights from item master data
        total_gross_weight = 0
        total_net_weight = 0

        for item in self.invoice_items_table or []:
            if item.item_code:
                try:
                    item_doc = frappe.get_doc("Item", item.item_code)
                    quantity = int(item.quantity or 0)

                    # Get weight from item master (standard Frappe Item fields)
                    gross_weight = flt(item_doc.get("weight_per_unit") or 0)
                    net_weight = flt(
                        item_doc.get("net_weight") or gross_weight
                    )  # Fallback to gross if net not available

                    total_gross_weight += gross_weight * quantity
                    total_net_weight += net_weight * quantity
                except Exception:
                    # If item doesn't exist or has no weight, continue
                    pass

        self.product_gross_weight = (
            str(total_gross_weight) if total_gross_weight > 0 else "0"
        )
        self.product_net_weight = str(total_net_weight) if total_net_weight > 0 else "0"

        # Calculate sum of all item amounts
        items_total = sum(flt(item.amount) for item in (self.invoice_items_table or []))

        # Add additional charges and subtract discounts
        self.total = (
            items_total
            + flt(self.total_freight)
            + flt(self.total_insurance)
            + flt(self.other_expenses)
            - flt(self.total_discount)
        )

        # Calculate total of taxes (sum of all individual tax values)
        self.total_of_taxes = (
            flt(self.icms_value or 0)
            + flt(self.ipi_value or 0)
            + flt(self.pis_value or 0)
            + flt(self.cofins_value or 0)
            + flt(self.difal_value or 0)
        )

        # Calculate total with taxes (total + total_of_taxes)
        self.total_with_taxes = self.total + self.total_of_taxes

    def calculate_taxes_from_template(self):
        """Calculate tax values from template - either from template values or automatically
        The document must be in Draft or Created status to perform calculations.
        This method:
        1. Gets tax template if selected
        2. For each tax (ICMS, IPI, PIS, COFINS):
           - If template requires automatic calculation: Call calculation API
           - If template has manual rate: Apply the rate manually
           - Otherwise: Set field to zero

        If an error occurs during Processing status, the status will be changed to Processing Error.
        """
        if not self.tax_template:
            return

        status_allowed = ["Draft", "Non Processed", "Processing"]
        if self.invoice_status not in status_allowed:
            return

        try:
            tax_template = frappe.get_doc("Tax", self.tax_template)
        except Exception as e:
            # If error occurs during Processing, change status to Processing Error
            if self.invoice_status == "Processing":
                self._handle_processing_error(
                    "Tax Template Error", f"Failed to fetch tax template: {str(e)}"
                )
            return

        # Check if any tax requires automatic calculation
        needs_auto_calculation = (
            tax_template.calculate_automatically_icms
            or tax_template.calculate_automatically_ipi
            or tax_template.calculate_automatically_pis
            or tax_template.calculate_automatically_cofins
        )

        if needs_auto_calculation:
            # Call NFe.io API for automatic calculation
            try:
                nfeio_tax.calculate_taxes(self, tax_template)
            except Exception as e:
                # If error occurs during Processing, change status to Processing Error
                if self.invoice_status == "Processing":
                    self._handle_processing_error(
                        "Tax Calculation Error", f"NFe.io API call failed: {str(e)}"
                    )
                    return
                else:
                    # Re-raise the exception for other statuses
                    raise

        # Calculate base for manual tax calculations (total product value)
        base_value = (
            sum(item.amount for item in self.invoice_items_table)
            if self.invoice_items_table
            else 0
        )

        # For taxes that don't require automatic calculation, apply manual rates or set to zero
        if not tax_template.calculate_automatically_icms:
            # Set ICMS value to zero (non-taxed)
            self.icms_value = 0.0

        if not tax_template.calculate_automatically_ipi:
            # Set IPI value to zero (non-taxed)
            self.ipi_value = 0.0

        if not tax_template.calculate_automatically_pis:
            # Apply manual PIS rate if configured, otherwise set to zero
            if hasattr(tax_template, "pis_rate") and tax_template.pis_rate:
                self.pis_value = base_value * (float(tax_template.pis_rate) / 100)
            else:
                self.pis_value = 0.0

        if not tax_template.calculate_automatically_cofins:
            # Apply manual COFINS rate if configured, otherwise set to zero
            if hasattr(tax_template, "cofins_rate") and tax_template.cofins_rate:
                self.cofins_value = base_value * (float(tax_template.cofins_rate) / 100)
            else:
                self.cofins_value = 0.0

        # DIFAL is typically not in templates, set to 0 for now
        if not hasattr(self, "difal_value") or self.difal_value is None:
            self.difal_value = 0.0

    def calculate_automatic_taxes(self):
        """Calculate ICMS and IPI automatically based on tax template using NFe.io API"""
        if not self.tax_template:
            return

        # Get the tax template document
        try:
            tax_template = frappe.get_doc("Tax", self.tax_template)
        except Exception:
            return

        # Calculate taxes using NFe.io API if either ICMS or IPI needs calculation
        if (
            tax_template.calculate_automatically_icms
            or tax_template.calculate_automatically_ipi
        ):
            nfeio_tax.calculate_taxes(self, tax_template)

    def on_update(self):
        frappe.log_error(f"Invoice document updated: {self.name}")

    def before_submit(self):
        """Validate invoice has PDF URL before submission"""
        if not self.invoice_link:
            frappe.throw(
                _(
                    "Cannot submit invoice without PDF URL. Please ensure the invoice has been processed and invoice_link field is set."
                )
            )

    def on_submit(self):
        # Chama o endpoint ou funcao da logistica (proxima etapa)
        frappe.log_error(f"Invoice document submitted: {self.name}")


@frappe.whitelist()
def move_to_processing(invoice_name):
    """
    API endpoint to transition invoice to Processing status and issue NFe invoice via NFe.io
    This is called from the form button
    
    Flow: This endpoint → nfeio.issue_product_invoice() → product_invoice.issue_product_invoice()
    """
    import random
    
    try:
        # Import nfeio module to call Layer 2
        from frappe_brazil_invoice.brazil_invoice.doctype.nfeio import nfeio
        
        # Get invoice document
        invoice_doc = frappe.get_doc("Product Invoice", invoice_name)
        
        # Build invoice data from Product Invoice document
        invoice_data = _build_invoice_data_from_doc(invoice_doc)
        
        # Call Layer 2: nfeio whitelisted endpoint (without document_name to avoid duplicate scheduling)
        result = nfeio.issue_product_invoice(invoice_data)
        
        # Handle error cases first (fail fast)
        if not result or not isinstance(result, dict) or not result.get("success"):
            error_msg = result.get("error", "Invalid response from NFe.io") if result else "No response from NFe.io"
            frappe.throw(f"Failed to issue invoice: {error_msg}")
        
        # Whitelisted endpoint returns {"success": True, "data": {...}}
        # Extract the actual NFe.io response from the "data" field
        nfeio_response = result.get("data", {})
        
        # Update invoice with NFe.io response
        invoice_id = nfeio_response.get("id")
        invoice_doc.invoice_id = invoice_id
        invoice_doc.invoice_status = "Processing"
        
        # Set flags to allow modifications during Processing status
        invoice_doc.flags.ignore_processing_lock = True
        invoice_doc.save()
        frappe.db.commit()
        
        # Schedule background status check jobs
        if not invoice_id:
            frappe.throw("Invoice ID not returned from NFe.io. Cannot schedule status checks.")
        
        # Helper function to schedule status check jobs
        def schedule_status_check(min_minutes, max_minutes, job_suffix):
            """Schedule a status check job with random delay within the specified range"""
            delay_seconds = random.randint(min_minutes, max_minutes) * 60
            frappe.enqueue(
                "frappe_brazil_invoice.brazil_invoice.doctype.product_invoice.product_invoice.check_invoice_status_and_update",
                queue="default",
                timeout=300,
                invoice_id=invoice_id,
                document_name=invoice_name,
                enqueue_after_commit=True,
                at_front=False,
                now=False,
                job_name=f"check_invoice_status_{invoice_id}_{job_suffix}",
                **{"in": delay_seconds}
            )
            return delay_seconds
        
        # Schedule three status checks at different intervals
        first_delay = schedule_status_check(3, 6, "first")
        second_delay = schedule_status_check(10, 20, "second")
        third_delay = schedule_status_check(30, 40, "third")
        
        frappe.logger().info(
            f"Scheduled 3 status checks for invoice {invoice_id} (doc: {invoice_name}) "
            f"at {first_delay//60}, {second_delay//60}, and {third_delay//60} minutes"
        )
        
        frappe.msgprint(
            f"Invoice sent to NFe.io successfully!<br>"
            f"Invoice ID: {nfeio_response.get('id')}<br>"
            f"Status: {nfeio_response.get('status', 'Processing')}<br>"
            f"The invoice is being processed. Check status for updates.",
            title="Success",
            indicator="green",
        )
        
        return {
            "success": True,
            "message": "Invoice sent to NFe.io successfully",
            "data": nfeio_response,
        }
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "NFe Invoice Creation Error")
        frappe.throw(f"An error occurred: {str(e)}")


@frappe.whitelist()
def move_to_issued(invoice_name, invoice_ref_series=None, invoice_ref_number=None, 
                   invoice_ref_access_key=None, invoice_serie=None, invoice_number=None, 
                   invoice_link=None):
    """
    Transition invoice to Issued status
    
    Required fields for Issued status:
    - invoice_ref_series: Invoice Ref. Series
    - invoice_ref_number: Invoice Ref. Number
    - invoice_ref_access_key: Invoice Ref. Access Key
    - invoice_serie: Invoice Serie
    - invoice_number: Invoice Number
    - invoice_link: Invoice Link
    
    Args:
        invoice_name: Name of the Product Invoice document
        invoice_ref_series: Invoice reference series
        invoice_ref_number: Invoice reference number
        invoice_ref_access_key: Invoice reference access key
        invoice_serie: Invoice series
        invoice_number: Invoice number
        invoice_link: Link to the invoice PDF
        
    Returns:
        dict: Response with success status and message
    """
    try:
        invoice_doc = frappe.get_doc("Product Invoice", invoice_name)
        
        # Update required fields if provided
        if invoice_ref_series:
            invoice_doc.invoice_ref_series = invoice_ref_series
        if invoice_ref_number:
            invoice_doc.invoice_ref_number = invoice_ref_number
        if invoice_ref_access_key:
            invoice_doc.invoice_ref_access_key = invoice_ref_access_key
        if invoice_serie:
            invoice_doc.invoice_serie = invoice_serie
        if invoice_number:
            invoice_doc.invoice_number = invoice_number
        if invoice_link:
            invoice_doc.invoice_link = invoice_link
        
        # Set status to Issued
        invoice_doc.invoice_status = "Issued"
        
        # Save will trigger validation of required fields
        invoice_doc.save()
        frappe.db.commit()
        
        frappe.msgprint(
            f"Invoice {invoice_name} successfully moved to Issued status",
            title="Success",
            indicator="green",
        )
        
        return {
            "success": True,
            "message": f"Invoice {invoice_name} moved to Issued status",
            "invoice_name": invoice_name,
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Move to Issued Error")
        frappe.throw(f"Failed to move invoice to Issued status: {str(e)}")


@frappe.whitelist()
def move_to_tax_calculation_error(invoice_name, error_message=None):
    """
    Transition invoice to Tax Calculation Error status
    
    This status is used when automatic tax calculation fails.
    No specific fields are required, but an error message should be logged.
    
    Args:
        invoice_name: Name of the Product Invoice document
        error_message: Optional error message to log
        
    Returns:
        dict: Response with success status and message
    """
    try:
        invoice_doc = frappe.get_doc("Product Invoice", invoice_name)
        
        # Set status to Tax Calculation Error
        invoice_doc.invoice_status = "Tax Calculation Error"
        
        # Log error if provided
        if error_message:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] [ERROR] Tax Calculation Error\\n  {error_message}"
            
            if invoice_doc.errors_field:
                invoice_doc.errors_field = invoice_doc.errors_field + "\\n\\n" + log_entry
            else:
                invoice_doc.errors_field = log_entry
        
        invoice_doc.save()
        frappe.db.commit()
        
        frappe.msgprint(
            f"Invoice {invoice_name} moved to Tax Calculation Error status",
            title="Status Updated",
            indicator="orange",
        )
        
        return {
            "success": True,
            "message": f"Invoice {invoice_name} moved to Tax Calculation Error status",
            "invoice_name": invoice_name,
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Move to Tax Calculation Error")
        frappe.throw(f"Failed to move invoice to Tax Calculation Error status: {str(e)}")


@frappe.whitelist()
def move_to_processing_error(invoice_name, error_message=None):
    """
    Transition invoice to Processing Error status
    
    This status is used when NFe.io processing fails.
    No specific fields are required, but an error message should be logged.
    
    Note: Per business rules, this status can only be reached from Processing status.
    
    Args:
        invoice_name: Name of the Product Invoice document
        error_message: Optional error message to log
        
    Returns:
        dict: Response with success status and message
    """
    try:
        invoice_doc = frappe.get_doc("Product Invoice", invoice_name)
        
        # Validate transition rule: Processing Error can only come from Processing
        if invoice_doc.invoice_status != "Processing":
            frappe.throw(
                f"Processing Error status can only be reached from Processing status. "
                f"Current status is '{invoice_doc.invoice_status}'."
            )
        
        # Set status to Processing Error
        invoice_doc.invoice_status = "Processing Error"
        
        # Log error if provided
        if error_message:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] [ERROR] Processing Error\\n  {error_message}"
            
            if invoice_doc.errors_field:
                invoice_doc.errors_field = invoice_doc.errors_field + "\\n\\n" + log_entry
            else:
                invoice_doc.errors_field = log_entry
        
        # Set flag to allow modifications during Processing status
        invoice_doc.flags.ignore_processing_lock = True
        invoice_doc.save()
        frappe.db.commit()
        
        frappe.msgprint(
            f"Invoice {invoice_name} moved to Processing Error status",
            title="Status Updated",
            indicator="red",
        )
        
        return {
            "success": True,
            "message": f"Invoice {invoice_name} moved to Processing Error status",
            "invoice_name": invoice_name,
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Move to Processing Error")
        frappe.throw(f"Failed to move invoice to Processing Error status: {str(e)}")


@frappe.whitelist()
def move_to_contingency(invoice_name):
    """
    Transition invoice to Contingency status
    
    This status is used for contingency invoices (offline issuance).
    No specific mandatory fields beyond the standard invoice fields.
    
    Args:
        invoice_name: Name of the Product Invoice document
        
    Returns:
        dict: Response with success status and message
    """
    try:
        invoice_doc = frappe.get_doc("Product Invoice", invoice_name)
        
        # Set status to Contingency
        invoice_doc.invoice_status = "Contingency"
        
        invoice_doc.save()
        frappe.db.commit()
        
        frappe.msgprint(
            f"Invoice {invoice_name} moved to Contingency status",
            title="Success",
            indicator="orange",
        )
        
        return {
            "success": True,
            "message": f"Invoice {invoice_name} moved to Contingency status",
            "invoice_name": invoice_name,
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Move to Contingency Error")
        frappe.throw(f"Failed to move invoice to Contingency status: {str(e)}")


@frappe.whitelist()
def move_to_rejected(invoice_name, rejection_reason=None):
    """
    Transition invoice to Rejected status
    
    This status is used when the fiscal authority rejects the invoice.
    No specific mandatory fields, but a rejection reason should be logged.
    
    Args:
        invoice_name: Name of the Product Invoice document
        rejection_reason: Optional rejection reason to log
        
    Returns:
        dict: Response with success status and message
    """
    try:
        invoice_doc = frappe.get_doc("Product Invoice", invoice_name)
        
        # Set status to Rejected
        invoice_doc.invoice_status = "Rejected"
        
        # Log rejection reason if provided
        if rejection_reason:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] [INFO] Invoice Rejected\\n  {rejection_reason}"
            
            if invoice_doc.errors_field:
                invoice_doc.errors_field = invoice_doc.errors_field + "\\n\\n" + log_entry
            else:
                invoice_doc.errors_field = log_entry
        
        invoice_doc.save()
        frappe.db.commit()
        
        frappe.msgprint(
            f"Invoice {invoice_name} moved to Rejected status",
            title="Status Updated",
            indicator="red",
        )
        
        return {
            "success": True,
            "message": f"Invoice {invoice_name} moved to Rejected status",
            "invoice_name": invoice_name,
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Move to Rejected Error")
        frappe.throw(f"Failed to move invoice to Rejected status: {str(e)}")


@frappe.whitelist()
def move_to_cancelled(invoice_name, cancellation_reason=None):
    """
    Transition invoice to Cancelled status
    
    This status is used when an issued invoice is cancelled.
    No specific mandatory fields, but a cancellation reason should be logged.
    
    Args:
        invoice_name: Name of the Product Invoice document
        cancellation_reason: Optional cancellation reason to log
        
    Returns:
        dict: Response with success status and message
    """
    try:
        invoice_doc = frappe.get_doc("Product Invoice", invoice_name)
        
        # Set status to Cancelled
        invoice_doc.invoice_status = "Cancelled"
        
        # Log cancellation reason if provided
        if cancellation_reason:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] [INFO] Invoice Cancelled\\n  {cancellation_reason}"
            
            if invoice_doc.errors_field:
                invoice_doc.errors_field = invoice_doc.errors_field + "\\n\\n" + log_entry
            else:
                invoice_doc.errors_field = log_entry
        
        invoice_doc.save()
        frappe.db.commit()
        
        frappe.msgprint(
            f"Invoice {invoice_name} moved to Cancelled status",
            title="Status Updated",
            indicator="red",
        )
        
        return {
            "success": True,
            "message": f"Invoice {invoice_name} moved to Cancelled status",
            "invoice_name": invoice_name,
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Move to Cancelled Error")
        frappe.throw(f"Failed to move invoice to Cancelled status: {str(e)}")


@frappe.whitelist()
def move_to_unused(invoice_name):
    """
    Transition invoice to Unused status
    
    This status is used to mark an invoice as unused/discarded.
    No specific mandatory fields required.
    
    Args:
        invoice_name: Name of the Product Invoice document
        
    Returns:
        dict: Response with success status and message
    """
    try:
        invoice_doc = frappe.get_doc("Product Invoice", invoice_name)
        
        # Set status to Unused
        invoice_doc.invoice_status = "Unused"
        
        invoice_doc.save()
        frappe.db.commit()
        
        frappe.msgprint(
            f"Invoice {invoice_name} moved to Unused status",
            title="Status Updated",
            indicator="grey",
        )
        
        return {
            "success": True,
            "message": f"Invoice {invoice_name} moved to Unused status",
            "invoice_name": invoice_name,
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Move to Unused Error")
        frappe.throw(f"Failed to move invoice to Unused status: {str(e)}")


@frappe.whitelist()
def get_invoice_status(invoice_name):
    """
    Get the current status of an NFe invoice from NFe.io
    
    Flow: This endpoint → nfeio.get_product_invoice_by_id() → product_invoice.get_product_invoice_by_id()
    """
    try:
        # Import nfeio module to call Layer 2
        from frappe_brazil_invoice.brazil_invoice.doctype.nfeio import nfeio
        
        # Get invoice document
        invoice_doc = frappe.get_doc("Product Invoice", invoice_name)
        
        if not invoice_doc.invoice_id:
            return {"success": False, "message": "Invoice has not been sent to NFe.io yet"}
        
        # Call Layer 2: nfeio whitelisted endpoint
        result = nfeio.get_product_invoice_by_id(invoice_doc.invoice_id)
        
        if result and isinstance(result, dict):
            # Update invoice with latest status from NFe.io
            _update_invoice_from_nfeio_response(invoice_doc, result)
            
            return {"success": True, "data": result}
        else:
            return {
                "success": False,
                "message": "Failed to retrieve invoice status from NFe.io",
            }
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "NFe Status Check Error")
        return {"success": False, "message": str(e)}


def _build_invoice_data_from_doc(invoice_doc):
    """
    Build invoice data dictionary from Product Invoice document for NFe.io API
    
    Args:
        invoice_doc: Product Invoice document
        
    Returns:
        dict: Invoice data formatted for NFe.io API
    """
    # Map client type to NFe.io format
    client_type_map = {
        "Individual": 0,  # Pessoa Física
        "Company": 1,      # Pessoa Jurídica
    }
    
    # Map ICMS contributor to stateTaxNumberIndicator
    # "Taxpayer" -> "TaxPayer", "Non-Taxpayer" -> "NonTaxPayer"
    state_tax_indicator_map = {
        "Taxpayer": "TaxPayer",
        "Non-Taxpayer": "NonTaxPayer",
        "Exempt": "Exempt",
    }
    
    # Build buyer information
    buyer = {
        "name": invoice_doc.client_name,
        "federalTaxNumber": int(''.join(filter(str.isdigit, str(invoice_doc.client_id_number)))),
        "type": client_type_map.get(invoice_doc.client_type, 1),
        "address": {
            "state": invoice_doc.delivery_state,
            "city": {
                "code": invoice_doc.delivery_ibge,
                "name": invoice_doc.city,
            },
            "district": invoice_doc.delivery_neighborhood,
            "street": invoice_doc.delivery_address,
            "number": invoice_doc.delivery_number_address or "S/N",
            "postalCode": ''.join(filter(str.isdigit, str(invoice_doc.delivery_cep))),
            "country": "Brasil",
        },
    }
    
    # Add stateTaxNumberIndicator based on ICMS taxpayer status
    if invoice_doc.icms_taxpayer:
        state_tax_indicator = state_tax_indicator_map.get(invoice_doc.icms_taxpayer)
        if state_tax_indicator:
            buyer["stateTaxNumberIndicator"] = state_tax_indicator
    
    # Add optional buyer fields
    if invoice_doc.client_email:
        buyer["email"] = invoice_doc.client_email
    if invoice_doc.delivery_complement:
        buyer["address"]["additionalInformation"] = invoice_doc.delivery_complement
    
    # Build items list
    items = []
    for item in invoice_doc.invoice_items_table:
        # Format NCM: remove dots/periods and any other formatting characters
        # NFe.io expects NCM without formatting (8 digits max)
        ncm = item.ncm or ""
        if ncm:
            ncm = ncm.replace(".", "").replace("-", "").strip()
        
        item_data = {
            "code": item.item_code,
            "description": item.description or item.item_name,
            "ncm": ncm,  # NCM without dots/formatting
            "cfop": 5102,  # Default CFOP - should be configurable
            "unit": "UN",
            "quantity": float(item.quantity),
            "unitAmount": float(item.rate),
            "totalAmount": float(item.amount),
        }
        
        # Add tax information if available
        # This would need to be enhanced based on tax template
        item_data["tax"] = {
            "icms": {
                "origin": "0",
                "cst": "00",
                "baseTax": float(item.amount),
                "rate": 18.0,
                "amount": float(item.amount) * 0.18,
            },
            "pis": {
                "cst": "01",
                "baseTax": float(item.amount),
                "rate": 1.65,
                "amount": float(item.amount) * 0.0165,
            },
            "cofins": {
                "cst": "01",
                "baseTax": float(item.amount),
                "rate": 7.6,
                "amount": float(item.amount) * 0.076,
            },
        }
        
        items.append(item_data)
    
    # Calculate totals
    total_items = sum(float(item.amount) for item in invoice_doc.invoice_items_table)
    
    invoice_data = {
        "operationNature": invoice_doc.operation_type or "VENDA DE MERCADORIA",
        "operationType": "Outgoing",
        "consumerType": "FinalConsumer",
        "body": invoice_doc.additional_information or "Nota fiscal de produto",
        "buyer": buyer,
        "items": items,
        "totals": {
            "icms": {
                "baseTax": total_items,
                "icmsAmount": float(invoice_doc.icms_value or 0),
                "productAmount": total_items,
                "pisAmount": float(invoice_doc.pis_value or 0),
                "cofinsAmount": float(invoice_doc.cofins_value or 0),
                "invoiceAmount": float(invoice_doc.total or total_items),
            }
        },
    }
    
    return invoice_data


def _update_invoice_from_nfeio_response(invoice_doc, nfeio_response):
    """
    Update Product Invoice document with data from NFe.io response
    
    Args:
        invoice_doc: Product Invoice document
        nfeio_response: Response from NFe.io API
    """
    try:
        # Update status based on NFe.io status
        nfeio_status = nfeio_response.get("status")
        status_map = {
            "Issued": "Issued",
            "Processing": "Processing",
            "Error": "Processing Error",
            "Rejected": "Rejected",
        }
        
        if nfeio_status in status_map:
            invoice_doc.invoice_status = status_map[nfeio_status]
        
        # Update invoice fields from NFe.io response
        if nfeio_response.get("serie"):
            invoice_doc.invoice_serie = str(nfeio_response.get("serie"))
        if nfeio_response.get("number"):
            invoice_doc.invoice_number = str(nfeio_response.get("number"))
        if nfeio_response.get("authorization", {}).get("accessKey"):
            invoice_doc.invoice_access_key = nfeio_response["authorization"]["accessKey"]
        
        # Reference fields for return invoices
        if nfeio_response.get("serie"):
            invoice_doc.invoice_ref_series = str(nfeio_response.get("serie"))
        if nfeio_response.get("number"):
            invoice_doc.invoice_ref_number = str(nfeio_response.get("number"))
        if nfeio_response.get("authorization", {}).get("accessKey"):
            invoice_doc.invoice_ref_access_key = nfeio_response["authorization"]["accessKey"]
        
        # Set flags to allow modifications during Processing status
        invoice_doc.flags.ignore_processing_lock = True
        invoice_doc.save()
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(
            f"Error updating invoice from NFe.io response: {str(e)}\n{frappe.get_traceback()}",
            "Invoice Update Error"
        )


@frappe.whitelist(allow_guest=False)
def create_invoice(
    operation_type=None,
    client_type=None,
    freight_modality=None,
    client_name=None,
    client_email=None,
    client_phone=None,
    client_id_number=None,
    icms_contributor=None,
    state_registration=None,
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
    product_type=None,
    carrier=None,
    additional_information=None,
    total_freight=None,
    total_discount=None,
    total_insurance=None,
    other_expenses=None,
    total_tax=None,
    tax_template=None,
    invoice_items_table=None,
    invoice_ref_series=None,
    invoice_ref_number=None,
    invoice_ref_access_key=None,
    is_return_invoice=None,
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
            icms_contributor (str): ICMS contributor status
            state_registration (str): State registration number
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
            product_type (str): Product type/species
            carrier (str): Carrier name or ID
            additional_information (str): Additional information for the invoice
            total_freight (float): Total freight value
            total_discount (float): Total discount value
            total_insurance (float): Total insurance value
            other_expenses (float): Other expenses
            total_tax (float): Total tax value
            tax_template (str): Tax template name or ID

    Note:
            The following fields are calculated automatically:
            - total (float): Calculated from items and additional charges
            - product_quantity (str): Calculated from sum of item quantities
            - product_gross_weight (str): Calculated from item weights
            - product_net_weight (str): Calculated from item weights

            invoice_items_table (list): List of invoice items (child table)
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

        missing_fields = [
            field for field, value in required_fields.items() if not value
        ]
        if missing_fields:
            return {
                "success": False,
                "message": f"Missing required fields: {', '.join(missing_fields)}",
                "docname": None,
            }

        # Validate items presence (string or list)
        parsed_items = None
        if invoice_items_table:
            if isinstance(invoice_items_table, str):
                try:
                    parsed_items = json.loads(invoice_items_table)
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "message": "invoice_items_table must be JSON list when provided as string",
                        "docname": None,
                    }
            elif isinstance(invoice_items_table, list):
                parsed_items = invoice_items_table
            else:
                return {
                    "success": False,
                    "message": "invoice_items_table must be a list of items",
                    "docname": None,
                }

        if not parsed_items or len(parsed_items) == 0:
            return {
                "success": False,
                "message": "Cannot create invoice without items (invoice_items_table).",
                "docname": None,
            }

        # Create new Invoice document
        invoice_doc = frappe.new_doc("Product Invoice")

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
        if icms_contributor:
            invoice_doc.icms_taxpayer = icms_contributor
        if state_registration:
            invoice_doc.state_registration = state_registration

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

        # Set product information (quantity and weights calculated automatically)
        if product_brand:
            invoice_doc.product_brand = product_brand
        if product_type:
            invoice_doc.product_type = product_type
        if carrier:
            invoice_doc.carrier = carrier

        # Set additional information
        if additional_information:
            invoice_doc.additional_information = additional_information

        # Set totals (total field is calculated automatically)
        if total_freight:
            invoice_doc.total_freight = total_freight
        if total_discount:
            invoice_doc.total_discount = total_discount
        if total_insurance:
            invoice_doc.total_insurance = total_insurance
        if other_expenses:
            invoice_doc.other_expenses = other_expenses
        # Note: total_of_taxes and total_with_taxes are calculated automatically

        # Set tax template
        if tax_template:
            invoice_doc.tax_template = tax_template

        # Set reference invoice information
        if invoice_ref_series:
            invoice_doc.invoice_ref_series = invoice_ref_series
        if invoice_ref_number:
            invoice_doc.invoice_ref_number = invoice_ref_number
        if invoice_ref_access_key:
            invoice_doc.invoice_ref_access_key = invoice_ref_access_key
        if is_return_invoice is not None:
            invoice_doc.is_return_invoice = is_return_invoice

        # Add invoice items (child table)
        for item in parsed_items:
            invoice_doc.append("invoice_items_table", item)

        # Insert the document (creates in Draft state)
        # Tag with test run token if present so summaries can scope to current run
        try:
            token = getattr(frappe.flags, "TEST_RUN_TOKEN", None)
        except Exception:
            token = None
        if token:
            marker = f"[TEST_RUN:{token}]"
            invoice_doc.status_reason = f"{(getattr(invoice_doc, 'status_reason', '') or '').strip()} {marker}".strip()
            invoice_doc.additional_information = f"{(getattr(invoice_doc, 'additional_information', '') or '').strip()} {marker}".strip()

        invoice_doc.insert(ignore_permissions=False)

        # Commit the transaction
        frappe.db.commit()

        return {
            "success": True,
            "docname": invoice_doc.name,
            "message": f"Invoice {invoice_doc.name} created successfully in draft state",
        }

    except frappe.ValidationError as e:
        frappe.db.rollback()
        frappe.log_error(
            title="Invoice Creation Validation Error", message=frappe.get_traceback()
        )
        return {"success": False, "message": str(e), "docname": None}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(title="Invoice Creation Error", message=frappe.get_traceback())
        return {
            "success": False,
            "message": f"An error occurred while creating the invoice: {str(e)}",
            "docname": None,
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
                "invoice": None,
            }

        # Check if invoice exists
        if not frappe.db.exists("Product Invoice", docname):
            return {
                "success": False,
                "message": f"Invoice {docname} does not exist",
                "invoice": None,
            }

        # Get the invoice document
        invoice_doc = frappe.get_doc("Product Invoice", docname)

        # Check permissions
        if not invoice_doc.has_permission("read"):
            return {
                "success": False,
                "message": "You do not have permission to read this invoice",
                "invoice": None,
            }

        return {
            "success": True,
            "invoice": invoice_doc.as_dict(),
            "message": f"Invoice {docname} retrieved successfully",
        }

    except Exception as e:
        frappe.log_error(
            title="Get Invoice Details Error", message=frappe.get_traceback()
        )
        return {
            "success": False,
            "message": f"An error occurred: {str(e)}",
            "invoice": None,
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
                    "failed_invoices": [],
                }

        if not isinstance(invoices_data, list):
            return {
                "success": False,
                "message": "invoices_data must be a list of invoice dictionaries",
                "created_invoices": [],
                "failed_invoices": [],
            }

        created_invoices = []
        failed_invoices = []

        for idx, invoice_data in enumerate(invoices_data):
            try:
                # Call the single invoice creation function
                result = create_invoice(**invoice_data)

                if result.get("success"):
                    created_invoices.append(
                        {"index": idx, "docname": result.get("docname")}
                    )
                else:
                    failed_invoices.append(
                        {
                            "index": idx,
                            "error": result.get("message"),
                            "data": invoice_data,
                        }
                    )

            except Exception as e:
                failed_invoices.append(
                    {"index": idx, "error": str(e), "data": invoice_data}
                )

        success = len(failed_invoices) == 0

        return {
            "success": success,
            "created_invoices": created_invoices,
            "failed_invoices": failed_invoices,
            "message": f"Created {len(created_invoices)} invoices successfully, {len(failed_invoices)} failed",
            "total_processed": len(invoices_data),
            "total_success": len(created_invoices),
            "total_failed": len(failed_invoices),
        }

    except Exception as e:
        frappe.log_error(
            title="Bulk Create Invoices Error", message=frappe.get_traceback()
        )
        return {
            "success": False,
            "message": f"An error occurred: {str(e)}",
            "created_invoices": [],
            "failed_invoices": [],
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
                    "failed_invoices": [],
                }

        if not isinstance(invoice_names, list):
            return {
                "success": False,
                "message": "invoice_names must be a list of invoice docnames",
                "processed_invoices": [],
                "failed_invoices": [],
            }

        processed_invoices = []
        failed_invoices = []

        for idx, invoice_name in enumerate(invoice_names):
            try:
                # Call the single invoice processing function
                result = move_to_processing(invoice_name)

                if result.get("success"):
                    processed_invoices.append(
                        {
                            "index": idx,
                            "docname": invoice_name,
                            "invoice_id": result.get("data", {}).get("id"),
                            "invoice_link": result.get("data", {}).get("pdf"),
                        }
                    )
                else:
                    failed_invoices.append(
                        {
                            "index": idx,
                            "docname": invoice_name,
                            "error": result.get("message", "Unknown error"),
                        }
                    )

            except Exception as e:
                failed_invoices.append(
                    {"index": idx, "docname": invoice_name, "error": str(e)}
                )

        success = len(failed_invoices) == 0

        return {
            "success": success,
            "processed_invoices": processed_invoices,
            "failed_invoices": failed_invoices,
            "message": f"Processed {len(processed_invoices)} invoices successfully, {len(failed_invoices)} failed",
            "total_processed": len(invoice_names),
            "total_success": len(processed_invoices),
            "total_failed": len(failed_invoices),
        }

    except Exception as e:
        frappe.log_error(
            title="Bulk Process Invoices Error", message=frappe.get_traceback()
        )
        return {
            "success": False,
            "message": f"An error occurred: {str(e)}",
            "processed_invoices": [],
            "failed_invoices": [],
        }


@frappe.whitelist()
def get_tax_template_query(doctype, txt, searchfield, start, page_len, filters):
    """
    Custom query for tax_template field - only show templates
    Returns tax records where is_template = 1 and displays template_name
    """
    return frappe.db.sql(
        """
		SELECT name, template_name
		FROM `tabTax`
		WHERE is_template = 1
			AND (name LIKE %(txt)s OR template_name LIKE %(txt)s)
		ORDER BY
			CASE WHEN name LIKE %(txt)s THEN 0 ELSE 1 END,
			template_name
		LIMIT %(start)s, %(page_len)s
	""",
        {"txt": "%" + txt + "%", "start": start, "page_len": page_len},
    )


def check_invoice_status_and_update(invoice_id, document_name):
    """
    Background job to check NFe.io invoice status and update Product Invoice document
    
    This function is called by scheduled jobs after invoice issuance to check the status
    and update the document accordingly.
    
    Args:
        invoice_id: NFe.io invoice ID
        document_name: Name of the Product Invoice document
    """
    from ..nfeio import product_invoice as nfeio_product_invoice
    
    try:
        # Get the Product Invoice document
        try:
            invoice_doc = frappe.get_doc("Product Invoice", document_name)
        except frappe.DoesNotExistError:
            frappe.log_error(
                f"Product Invoice '{document_name}' not found for status check",
                "Invoice Status Check Error"
            )
            return
        
        # Check if document is still in "Processing" status
        if invoice_doc.invoice_status != "Processing":
            frappe.logger().info(
                f"Invoice {document_name} is no longer in Processing status. "
                f"Current status: {invoice_doc.invoice_status}. Skipping status check."
            )
            return
        
        # Get valid NFe.io configuration
        from ..nfeio.nfeio import _get_valid_nfeio_config
        nfeio_config = _get_valid_nfeio_config()
        if not nfeio_config:
            frappe.log_error(
                f"No valid NFe.io configuration found for invoice {document_name}",
                "Invoice Status Check Error"
            )
            return
        
        # Get invoice status from NFe.io
        nfeio_invoice = nfeio_product_invoice.get_product_invoice_by_id(invoice_id, nfeio_config)
        
        if not nfeio_invoice:
            frappe.log_error(
                f"Could not retrieve invoice {invoice_id} from NFe.io for document {document_name}",
                "Invoice Status Check Error"
            )
            return
        
        # Check NFe.io invoice status (flowStatus field)
        flow_status = nfeio_invoice.get("flowStatus", "").lower()
        
        # Handle error/rejected status
        if flow_status in ["error", "erro", "rejected", "rejeitado", "rejection"]:
            # Update document to Processing Error status
            invoice_doc.invoice_status = "Processing Error"
            
            # Get error message from various possible fields
            error_message = (
                nfeio_invoice.get("statusMessage") or 
                nfeio_invoice.get("message") or 
                nfeio_invoice.get("errorMessage") or
                f"Invoice processing failed with status: {nfeio_invoice.get('flowStatus')}"
            )
            invoice_doc.status_reason = error_message
            
            # Store the NFe.io invoice ID
            invoice_doc.invoice_id = invoice_id
            
            # Log errors if available
            if nfeio_invoice.get("errors"):
                error_log = json.dumps(nfeio_invoice.get("errors"), indent=2)
                invoice_doc.errors_field = error_log
            
            invoice_doc.save(ignore_permissions=True)
            frappe.db.commit()
            
            frappe.log_error(
                f"Invoice {document_name} (NFe.io ID: {invoice_id}) has error status: {flow_status}\n"
                f"Error message: {error_message}",
                "NFe Error Status"
            )
            frappe.logger().warning(
                f"Invoice {document_name} moved to Processing Error status due to: {error_message}"
            )
        
        # Handle issued/authorized status
        elif flow_status in ["issued", "emitido", "authorized", "autorizado", "authorised"]:
            # Get PDF URL
            pdf_url = None
            try:
                pdf_response = nfeio_product_invoice.get_invoice_pdf(invoice_id, nfeio_config, force=True)
                pdf_url = pdf_response.get("uri") if pdf_response else None
            except Exception as e:
                frappe.logger().warning(f"Could not get PDF for invoice {invoice_id}: {str(e)}")
            
            # Get XML URL
            xml_url = None
            try:
                xml_response = nfeio_product_invoice.get_invoice_xml(invoice_id, nfeio_config)
                xml_url = xml_response.get("uri") if xml_response else None
            except Exception as e:
                frappe.logger().warning(f"Could not get XML for invoice {invoice_id}: {str(e)}")
            
            # Update document with invoice details
            invoice_doc.invoice_status = "Issued"
            invoice_doc.status_reason = "Invoice successfully issued and authorized by SEFAZ"
            invoice_doc.invoice_id = invoice_id
            
            # Update invoice links
            if pdf_url:
                invoice_doc.invoice_link = pdf_url
            
            # Update NFe details from response
            if nfeio_invoice.get("accessKey"):
                invoice_doc.invoice_access_key = nfeio_invoice.get("accessKey")
            if nfeio_invoice.get("number"):
                invoice_doc.invoice_number = str(nfeio_invoice.get("number"))
            if nfeio_invoice.get("serie"):
                invoice_doc.invoice_serie = str(nfeio_invoice.get("serie"))
            
            invoice_doc.save(ignore_permissions=True)
            frappe.db.commit()
            
            frappe.logger().info(
                f"Invoice {document_name} successfully issued. NFe.io ID: {invoice_id}, "
                f"Access Key: {invoice_doc.invoice_access_key}, Number: {invoice_doc.invoice_number}"
            )
        
        else:
            # Still processing or other intermediate status
            frappe.logger().info(
                f"Invoice {document_name} status: {flow_status}. Keeping in Processing state."
            )
    
    except nfeio_product_invoice.NFeIOAPIError as e:
        frappe.log_error(
            f"NFe.io API Error checking status for invoice {document_name}: {str(e)}\n{frappe.get_traceback()}",
            "Invoice Status Check API Error"
        )
    except Exception as e:
        frappe.log_error(
            f"Error checking invoice status for {document_name}: {str(e)}\n{frappe.get_traceback()}",
            "Invoice Status Check Error"
        )
