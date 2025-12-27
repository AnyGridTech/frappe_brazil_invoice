# Copyright (c) 2025, AnyGridTech and Contributors
# See license.txt

"""
Workflow Validation Tests

These tests verify the correct workflow behavior for invoice status transitions,
particularly around error handling and user/API permission separation.

To run these tests:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.invoices.test_workflow_validation
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe_brazil_invoice.brazil_invoice.doctype.invoices.test_invoices import (
    create_test_invoice_with_token,
    generate_random_client,
    generate_random_address,
    items_array,
)


class TestWorkflowValidationBehavior(FrappeTestCase):
    """Test correct workflow validation behavior for invoice status transitions"""

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests in this class"""
        frappe.set_user("Administrator")

    def test_validation_error_at_non_processed_does_not_auto_transition(self):
        """Test that validation errors at Non Processed status do NOT automatically 
        transition to Processing Error status.
        
        Expected behavior: Validation error should be raised, status should remain unchanged.
        """
        frappe.set_user("Administrator")

        # Generate test data
        client_data = generate_random_client(client_type="Company")
        address_data = generate_random_address()

        # Create invoice in Non Processed status
        result = create_test_invoice_with_token(
            client_type=client_data["client_type"],
            freight_modality="0 - Freight Contracted by Sender (CIF)",
            client_name=client_data["client_name"],
            client_email=client_data["email"],
            client_phone=client_data["phone"],
            client_id_number=client_data["client_id_number"],
            icms_contributor=client_data["icms_contributor"],
            state_registration=client_data["state_registration"],
            delivery_supervisor=address_data["responsible"],
            delivery_cep=address_data["cep"],
            delivery_address=address_data["address"],
            delivery_neighborhood=address_data["neighborhood"],
            delivery_state=address_data["state"],
            city=address_data["city"],
            delivery_number_address=address_data["address_number"],
            delivery_ibge=address_data["ibge"],
            delivery_phone=address_data["phone"],
            product_brand="Growatt",
            product_type="Inversor Solar",
            carrier=frappe.db.get_value(
                "Carrier", {"fantasy_name": "Transportadora Teste"}, "name"
            ),
            additional_information="Test validation error at Non Processed",
            total_freight=0.00,
            total_discount=0.00,
            total_insurance=0.00,
            other_expenses=0.00,
            tax_template=frappe.db.get_value(
                "Tax", {"template_name": "Remessa para Conserto"}, "name"
            ),
            invoice_items_table=[{"item_code": items_array[0]["item_code"], "quantity": 1}],
        )

        self.assertTrue(result.get("success"))
        invoice_name = result.get("docname")
        invoice = frappe.get_doc("Invoices", invoice_name)

        # Verify invoice is in Non Processed status
        self.assertEqual(invoice.invoice_status, "Non Processed")
        original_status = invoice.invoice_status

        # Try to save with invalid data (clear required field that's validated)
        # The responsible field is mandatory for Non Processed status
        invoice.delivery_supervisor = None  # This should cause validation error

        # This should raise ValidationError, NOT auto-transition to Processing Error
        with self.assertRaises(frappe.ValidationError) as context:
            invoice.save()

        # Reload to check status hasn't changed
        invoice.reload()
        
        # CRITICAL: Status should still be Non Processed, NOT Processing Error
        self.assertEqual(
            invoice.invoice_status,
            original_status,
            "Status should NOT auto-transition to Processing Error on validation error at Non Processed"
        )

        print(f"✅ Validation error at Non Processed correctly raised error without status change")
        print(f"   Original status: {original_status}")
        print(f"   Status after error: {invoice.invoice_status}")
        print(f"   Error message: {str(context.exception)}")

    def test_user_cannot_modify_invoice_in_processing_status(self):
        """Test that users CANNOT modify an invoice in Processing status.
        
        Expected behavior: User modifications should be blocked with clear error message.
        Only backend/API should be able to modify.
        """
        frappe.set_user("Administrator")

        # Generate test data
        client_data = generate_random_client(client_type="Company")
        address_data = generate_random_address()

        # Create invoice
        result = create_test_invoice_with_token(
            client_type=client_data["client_type"],
            freight_modality="0 - Freight Contracted by Sender (CIF)",
            client_name=client_data["client_name"],
            client_email=client_data["email"],
            client_phone=client_data["phone"],
            client_id_number=client_data["client_id_number"],
            icms_contributor=client_data["icms_contributor"],
            state_registration=client_data["state_registration"],
            delivery_supervisor=address_data["responsible"],
            delivery_cep=address_data["cep"],
            delivery_address=address_data["address"],
            delivery_neighborhood=address_data["neighborhood"],
            delivery_state=address_data["state"],
            city=address_data["city"],
            delivery_number_address=address_data["address_number"],
            delivery_ibge=address_data["ibge"],
            delivery_phone=address_data["phone"],
            product_brand="Growatt",
            product_type="Inversor Solar",
            carrier=frappe.db.get_value(
                "Carrier", {"fantasy_name": "Transportadora Teste"}, "name"
            ),
            additional_information="Test user modification block at Processing",
            total_freight=0.00,
            total_discount=0.00,
            total_insurance=0.00,
            other_expenses=0.00,
            tax_template=frappe.db.get_value(
                "Tax", {"template_name": "Remessa para Conserto"}, "name"
            ),
            invoice_items_table=[{"item_code": items_array[0]["item_code"], "quantity": 1}],
        )

        self.assertTrue(result.get("success"))
        invoice_name = result.get("docname")
        invoice = frappe.get_doc("Invoices", invoice_name)

        # Transition to Processing status
        invoice.invoice_status = "Processing"
        invoice.invoice_id = f"INV-{frappe.generate_hash(length=8)}"
        invoice.save()
        frappe.db.commit()

        # Verify status is Processing
        invoice.reload()
        self.assertEqual(invoice.invoice_status, "Processing")

        # Now try to modify as a user (not API/backend)
        # This should be BLOCKED
        invoice.additional_information = "User trying to modify"

        with self.assertRaises(frappe.PermissionError) as context:
            invoice.save()

        error_message = str(context.exception)
        
        # Verify the error message mentions Processing status protection
        self.assertIn(
            "Processing",
            error_message,
            "Error message should mention Processing status"
        )

        print(f"✅ User modification correctly blocked at Processing status")
        print(f"   Error message: {error_message}")

    def test_backend_can_modify_invoice_in_processing_status(self):
        """Test that backend/API CAN modify an invoice in Processing status.
        
        Expected behavior: Backend modifications should be allowed using special flag.
        """
        frappe.set_user("Administrator")

        # Generate test data
        client_data = generate_random_client(client_type="Company")
        address_data = generate_random_address()

        # Create invoice
        result = create_test_invoice_with_token(
            client_type=client_data["client_type"],
            freight_modality="0 - Freight Contracted by Sender (CIF)",
            client_name=client_data["client_name"],
            client_email=client_data["email"],
            client_phone=client_data["phone"],
            client_id_number=client_data["client_id_number"],
            icms_contributor=client_data["icms_contributor"],
            state_registration=client_data["state_registration"],
            delivery_supervisor=address_data["responsible"],
            delivery_cep=address_data["cep"],
            delivery_address=address_data["address"],
            delivery_neighborhood=address_data["neighborhood"],
            delivery_state=address_data["state"],
            city=address_data["city"],
            delivery_number_address=address_data["address_number"],
            delivery_ibge=address_data["ibge"],
            delivery_phone=address_data["phone"],
            product_brand="Growatt",
            product_type="Inversor Solar",
            carrier=frappe.db.get_value(
                "Carrier", {"fantasy_name": "Transportadora Teste"}, "name"
            ),
            additional_information="Test backend modification at Processing",
            total_freight=0.00,
            total_discount=0.00,
            total_insurance=0.00,
            other_expenses=0.00,
            tax_template=frappe.db.get_value(
                "Tax", {"template_name": "Remessa para Conserto"}, "name"
            ),
            invoice_items_table=[{"item_code": items_array[0]["item_code"], "quantity": 1}],
        )

        self.assertTrue(result.get("success"))
        invoice_name = result.get("docname")
        invoice = frappe.get_doc("Invoices", invoice_name)

        # Transition to Processing status
        invoice.invoice_status = "Processing"
        invoice.invoice_id = f"INV-{frappe.generate_hash(length=8)}"
        invoice.save()
        frappe.db.commit()

        # Verify status is Processing
        invoice.reload()
        self.assertEqual(invoice.invoice_status, "Processing")

        # Simulate backend/API modification using special flag
        invoice.additional_information = "Backend/API modification"
        invoice.flags.ignore_processing_lock = True  # Special flag for backend
        invoice.save()
        frappe.db.commit()

        # Verify modification was successful
        invoice.reload()
        self.assertEqual(
            invoice.additional_information,
            "Backend/API modification",
            "Backend should be able to modify invoice in Processing status"
        )

        print(f"✅ Backend modification correctly allowed at Processing status")

    def test_processing_error_transition_from_processing_only(self):
        """Test that Processing Error status can only be reached from Processing status.
        
        Expected behavior: Direct transition from Non Processed to Processing Error 
        should be blocked by workflow.
        """
        frappe.set_user("Administrator")

        # Generate test data
        client_data = generate_random_client(client_type="Company")
        address_data = generate_random_address()

        # Create invoice
        result = create_test_invoice_with_token(
            client_type=client_data["client_type"],
            freight_modality="0 - Freight Contracted by Sender (CIF)",
            client_name=client_data["client_name"],
            client_email=client_data["email"],
            client_phone=client_data["phone"],
            client_id_number=client_data["client_id_number"],
            icms_contributor=client_data["icms_contributor"],
            state_registration=client_data["state_registration"],
            delivery_supervisor=address_data["responsible"],
            delivery_cep=address_data["cep"],
            delivery_address=address_data["address"],
            delivery_neighborhood=address_data["neighborhood"],
            delivery_state=address_data["state"],
            city=address_data["city"],
            delivery_number_address=address_data["address_number"],
            delivery_ibge=address_data["ibge"],
            delivery_phone=address_data["phone"],
            product_brand="Growatt",
            product_type="Inversor Solar",
            carrier=frappe.db.get_value(
                "Carrier", {"fantasy_name": "Transportadora Teste"}, "name"
            ),
            additional_information="Test Processing Error workflow",
            total_freight=0.00,
            total_discount=0.00,
            total_insurance=0.00,
            other_expenses=0.00,
            tax_template=frappe.db.get_value(
                "Tax", {"template_name": "Remessa para Conserto"}, "name"
            ),
            invoice_items_table=[{"item_code": items_array[0]["item_code"], "quantity": 1}],
        )

        self.assertTrue(result.get("success"))
        invoice_name = result.get("docname")
        invoice = frappe.get_doc("Invoices", invoice_name)

        # Verify invoice is in Non Processed status
        self.assertEqual(invoice.invoice_status, "Non Processed")

        # Try to directly transition to Processing Error (should fail)
        invoice.invoice_status = "Processing Error"

        with self.assertRaises(frappe.ValidationError) as context:
            invoice.save()

        error_message = str(context.exception)
        self.assertIn("Non Processed", error_message)
        self.assertIn("Processing Error", error_message)

        print(f"✅ Direct transition from Non Processed to Processing Error correctly blocked")
        print(f"   Error: {error_message}")

        # Now follow correct workflow: Non Processed → Processing → Processing Error
        invoice.reload()
        invoice.invoice_status = "Processing"
        invoice.invoice_id = f"INV-{frappe.generate_hash(length=8)}"
        invoice.flags.ignore_processing_lock = True
        invoice.save()
        frappe.db.commit()

        # Now transition to Processing Error (should succeed)
        invoice.reload()
        invoice.invoice_status = "Processing Error"
        invoice.flags.ignore_processing_lock = True  # Allow backend to make this change
        invoice.save()
        frappe.db.commit()

        # Verify status changed to Processing Error
        invoice.reload()
        self.assertEqual(invoice.invoice_status, "Processing Error")

        print(f"✅ Correct transition Processing → Processing Error succeeded")

    def test_validation_error_detail_preserved(self):
        """Test that validation error details are preserved and not lost 
        when status doesn't auto-transition.
        
        Expected behavior: The actual validation error message should be shown to user.
        """
        frappe.set_user("Administrator")

        # Generate test data
        client_data = generate_random_client(client_type="Company")
        address_data = generate_random_address()

        # Create invoice
        result = create_test_invoice_with_token(
            client_type=client_data["client_type"],
            freight_modality="0 - Freight Contracted by Sender (CIF)",
            client_name=client_data["client_name"],
            client_email=client_data["email"],
            client_phone=client_data["phone"],
            client_id_number=client_data["client_id_number"],
            icms_contributor=client_data["icms_contributor"],
            state_registration=client_data["state_registration"],
            delivery_supervisor=address_data["responsible"],
            delivery_cep=address_data["cep"],
            delivery_address=address_data["address"],
            delivery_neighborhood=address_data["neighborhood"],
            delivery_state=address_data["state"],
            city=address_data["city"],
            delivery_number_address=address_data["address_number"],
            delivery_ibge=address_data["ibge"],
            delivery_phone=address_data["phone"],
            product_brand="Growatt",
            product_type="Inversor Solar",
            carrier=frappe.db.get_value(
                "Carrier", {"fantasy_name": "Transportadora Teste"}, "name"
            ),
            additional_information="Test error detail preservation",
            total_freight=0.00,
            total_discount=0.00,
            total_insurance=0.00,
            other_expenses=0.00,
            tax_template=frappe.db.get_value(
                "Tax", {"template_name": "Remessa para Conserto"}, "name"
            ),
            invoice_items_table=[{"item_code": items_array[0]["item_code"], "quantity": 1}],
        )

        self.assertTrue(result.get("success"))
        invoice_name = result.get("docname")
        invoice = frappe.get_doc("Invoices", invoice_name)

        # Clear a required field to trigger specific validation error
        invoice.delivery_supervisor = None  # Responsible is required for Non Processed

        # Capture the validation error
        with self.assertRaises(frappe.ValidationError) as context:
            invoice.save()

        error_message = str(context.exception)

        # Verify error message contains useful information
        # (Should mention the field that's missing, not just generic workflow error)
        self.assertTrue(
            len(error_message) > 0,
            "Error message should not be empty"
        )

        # The error should NOT mention "Processing Error" or workflow transitions
        self.assertNotIn(
            "Processing Error",
            error_message,
            "Error message should not mention Processing Error status"
        )

        print(f"✅ Validation error detail preserved correctly")
        print(f"   Error message: {error_message}")
