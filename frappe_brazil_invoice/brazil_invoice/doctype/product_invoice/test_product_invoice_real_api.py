# Copyright (c) 2025, AnyGridTech and Contributors
# See license.txt

"""
Real API Integration Tests for Product Invoice

**IMPORTANT**: These tests require:
1. A valid NFe.io configuration in the NFeIO doctype with:
   - company_id
   - api_token
   - can have is_test_config = 0 or 1

**NOTE**: Some tests may fail if invoices haven't been fully processed by SEFAZ:
- PDF/XML retrieval requires invoice to be in "Issued" status
- Cancellation requires invoice to be in "Issued" status
- In homologation environment, invoices may take time to process or may not complete

To run these tests:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.product_invoice.test_product_invoice_real_api
"""

import json
import frappe
from frappe.tests.utils import FrappeTestCase
from datetime import datetime

# Import shared test helpers
from .test_helpers import (
    create_test_carrier,
    create_test_tax_template,
    get_test_run_token,
    create_test_invoice_with_token,
    create_test_item,
    create_test_serial_no,
    generate_random_client_cnpj,
    generate_random_totals,
    generate_random_address,
    items_array,
    get_serial_no_array_test,
    move_invoice_to_processing,
    carriers_test,
    tax_array_test,
)


# Get test run token
TEST_RUN_TOKEN = get_test_run_token()

# Test execution tracking
test_results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "errors": [],
    "invoice_docnames": [],
    "start_time": None,
    "end_time": None,
}


def setUpModule():
    """Set up test data once for the entire module"""
    test_results["start_time"] = datetime.now()
    print("\nSetting up Product Invoice Real API test module")


def tearDownModule():
    """Clean up test data after all tests in the module"""
    test_results["end_time"] = datetime.now()
    print("\nTearing down Product Invoice Real API test module")
    print_test_dashboard()


def print_test_dashboard():
    """Print a formatted dashboard with test results"""
    width = 80

    print("\n" + "=" * width)
    print("PRODUCT INVOICE REAL API TEST DASHBOARD".center(width))
    print("=" * width)

    # Time information
    if test_results["start_time"] and test_results["end_time"]:
        duration = test_results["end_time"] - test_results["start_time"]
        print(f"\n⏱  Duration: {duration.total_seconds():.2f}s")

    # Test summary
    print("\n📊 TEST SUMMARY")
    print(f"   Total Tests:    {test_results['total']}")
    print(
        f"   ✓ Passed:       {test_results['passed']} ({test_results['passed']/max(test_results['total'],1)*100:.1f}%)"
    )
    print(f"   ✗ Failed:       {test_results['failed']}")
    print(f"   ⊘ Skipped:      {test_results['skipped']}")

    # Invoice information
    if test_results["invoice_docnames"]:
        print("\n📄 INVOICES CREATED")
        for idx, invoice_name in enumerate(test_results["invoice_docnames"], 1):
            print(f"   Invoice {idx}: {invoice_name}")

    # Error details
    if test_results["errors"]:
        print("\n⚠  ERRORS & WARNINGS")
        for error in test_results["errors"][:5]:  # Show max 5 errors
            print(f"   • {error}")
        if len(test_results["errors"]) > 5:
            print(f"   ... and {len(test_results['errors']) - 5} more")

    print("\n" + "=" * width)
    print()


# ============================================================================
# HELPER FUNCTIONS - DRY Principles
# ============================================================================


def cancel_invoice_with_retries(invoice, reason, max_retries=3, retry_delay=5):
    """
    Cancel invoice via API with retry logic.

    Args:
        invoice: Product Invoice document
        reason: Cancellation reason
        max_retries: Number of retry attempts
        retry_delay: Seconds to wait between retries

    Returns:
        dict: {'success': bool, 'error': str (if applicable)}
    """
    import time
    from frappe_brazil_invoice.brazil_invoice.doctype.nfeio import nfeio

    print(f"\n🗑️ Cancelling {invoice.name}...")
    print(f"  Status before cancellation: {invoice.invoice_status}")

    for attempt in range(1, max_retries + 1):
        try:
            print(f"  Attempt {attempt}/{max_retries} to cancel invoice...")

            # Cancel invoice via NFe.io API
            cancel_result = nfeio.cancel_product_invoice(invoice.invoice_id, reason)

            if cancel_result.get("success"):
                # Update invoice status to Unused
                invoice.invoice_status = "Unused"
                invoice.flags.ignore_processing_lock = True
                invoice.save()
                frappe.db.commit()
                invoice.reload()

                print(f"  Status after cancellation: {invoice.invoice_status}")
                print("  ✅ Invoice cancelled successfully")
                return {"success": True}
            else:
                error_msg = cancel_result.get("error", "Unknown error")
                if attempt < max_retries:
                    print(
                        f"  ⚠️ Cancellation failed: {error_msg}. Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                else:
                    return {"success": False, "error": error_msg}

        except Exception as e:
            if attempt < max_retries:
                print(
                    f"  ⚠️ Exception occurred: {str(e)}. Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
            else:
                return {"success": False, "error": str(e)}

    return {"success": False, "error": f"Failed after {max_retries} attempts"}


def wait_for_sefaz_processing(seconds=20):
    """
    Wait for SEFAZ to process the invoice.

    Args:
        seconds: Number of seconds to wait
    """
    import time

    print(f"  ⏳ Waiting {seconds} seconds for SEFAZ processing...")
    time.sleep(seconds)


def check_invoice_processing(invoice_doc):
    """
    Check if invoice has Processing Error status and print detailed debug info.

    Args:
        invoice: Product Invoice document
        invoice_number: Invoice number for display (1 or 2)

    Returns:
        dict: {'error': bool, 'reason': str}
    """
    print(f"\n🔄 Running handle_invoice_status_update for {invoice_doc.name}...")
    print(f"  Invoice ID: {invoice_doc.invoice_id}")
    print(f"  Status before check: {invoice_doc.invoice_status}")

    # Wait for SEFAZ processing
    wait_for_sefaz_processing(10)

    # Call the background job function directly
    try:
        from frappe_brazil_invoice.brazil_invoice.doctype.nfeio.webhook import (
            handle_invoice_status_update,
        )

        data = {"id": invoice_doc.invoice_id}

        handle_invoice_status_update(data)
    except Exception as e:
        return {
            "error": True,
            "invoice_doc": invoice_doc,
            "reason": f"Exception during status check: {str(e)}",
        }

    # Reload invoice to get updated data
    invoice_doc.reload()
    print(f"  Status after check: {invoice_doc.invoice_status}")
    print(f"  Status Reason: {invoice_doc.status_reason or 'Not set'}")
    print(
        f"  Access Key: {getattr(invoice_doc, 'invoice_access_key', None) or 'Not set'}"
    )
    print(f"  Number: {getattr(invoice_doc, 'invoice_number', None) or 'Not set'}")
    print(f"  Serie: {getattr(invoice_doc, 'invoice_serie', None) or 'Not set'}")
    print(f"  PDF Link: {getattr(invoice_doc, 'invoice_pdf_url', None) or 'Not set'}")

    if invoice_doc.invoice_status == "Issued":
        return {"error": False, "reason": None}

    print("\n" + "=" * 70)
    print("❌ INVOICE PROCESSING FAILURE DETECTED")

    try:
        import pprint

        print("\nFull invoice data from Doctype for debugging:")
        invoice_doc_dict = invoice_doc.as_dict()
        pprint.pprint(invoice_doc_dict, width=60, indent=2)
    except Exception as e:
        print(f"Error printing invoice data: {str(e)}")
    # try:
    #     invoice_doc_dict = invoice_doc.as_dict()
    #     print("\nFull invoice data from Doctype for debugging:")
    #     print(json.dumps(invoice_doc_dict, indent=2, ensure_ascii=False))
    # except Exception as e:
    #     print(f"Error printing invoice doctype data: {str(e)}")

    try:
        from frappe_brazil_invoice.brazil_invoice.doctype.nfeio import nfeio

        invoice_data = nfeio.get_product_invoice_by_id(invoice_doc.invoice_id)
        print("\nFull invoice data from NFe.io API for debugging:")
        print(json.dumps(invoice_data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error fetching invoice data from NFe.io: {str(e)}")

    print("=" * 70 + "\n")

    return {"error": True, "reason": invoice_doc.status_reason}


class TestProductInvoiceRealAPI(FrappeTestCase):
    """Real API integration tests for Product Invoice DocType"""

    # Class variables to track invoice error states
    invoice_1_error = False
    invoice_2_error = False
    # Class variable to store serial numbers for reuse across tests
    test_serial_numbers = None

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests"""
        frappe.set_user("Administrator")

        # Check if NFe.io configuration exists (test configs only)
        # Get test config with highest usage_priority
        nfeio_configs = frappe.get_all(
            "NFeIO",
            fields=["name", "company_id", "is_test_config", "usage_priority"],
            filters={"is_test_config": 1},
            order_by="usage_priority DESC",
            limit=1
        )

        if not nfeio_configs:
            cls.skip_tests = True
            print(
                "\nSkipping Product Invoice Real API tests: No NFe.io test configuration found."
            )
            print("   Please create an NFeIO document with api_token and is_test_config=1")
            return

        cls.skip_tests = False
        cls.nfeio_config_name = nfeio_configs[0]["name"]
        print(
            f"\n✓ Using NFe.io configuration: {cls.nfeio_config_name} (is_test_config={nfeio_configs[0]['is_test_config']}, usage_priority={nfeio_configs[0]['usage_priority']})"
        )

        # Create test items using shared helper
        for item_data in items_array:
            create_test_item(**item_data)

        # Create test serial numbers using the stored serial numbers
        for serial_data in cls.test_serial_numbers:
            create_test_serial_no(**serial_data)

        # Create test carriers using shared helper data
        for carrier_data in carriers_test:
            create_test_carrier(**carrier_data)
        
        # Create test tax templates in case they're not present
        for tax_template in tax_array_test:
            create_test_tax_template(**tax_template)

        # Generate serial numbers ONCE and store in class variable for reuse
        cls.test_serial_numbers = get_serial_no_array_test()

    def setUp(self):
        """Set up each test and track execution"""
        if self.skip_tests:
            self.skipTest("No valid NFe.io configuration found")

        test_results["total"] += 1

    def tearDown(self):
        """Track test results after each test"""
        # Check test outcome
        if hasattr(self, "_outcome"):
            result = self._outcome.result

            # Check for failures first (AssertionError from self.fail())
            if result.failures and any(test == self for test, _ in result.failures):
                test_results["failed"] += 1
                failure_info = next(
                    (traceback for test, traceback in result.failures if test == self),
                    "Unknown failure",
                )
                error_msg = str(failure_info).split("\n")[-1][:150]
                test_results["errors"].append(f"{self._testMethodName}: {error_msg}")
            # Then check for errors (exceptions)
            elif result.errors and any(test == self for test, _ in result.errors):
                test_results["failed"] += 1
                error_info = next(
                    (traceback for test, traceback in result.errors if test == self),
                    "Unknown error",
                )
                error_msg = str(error_info).split("\n")[-1][:150]
                test_results["errors"].append(f"{self._testMethodName}: {error_msg}")
            # Then check for skipped
            elif result.skipped and any(test == self for test, _ in result.skipped):
                test_results["skipped"] += 1
            # Otherwise it passed
            else:
                test_results["passed"] += 1

    def test_001_create_and_issue_invoice_cnpj_nontaxpayer(self):
        """Create and Issue
        Invoice Type: Product Invoice
        Client Type: CNPJ
        ICMS Type: Non-Taxpayer
        Operation Type: Internal (SP to SP)
        Operation Nature: Repair Shipment
        Expected Result: Invoice created and issued successfully
        """
        frappe.set_user("Administrator")

        # Generate random totals
        totals_data = generate_random_totals()

        # Generate random address in SP (internal operation)
        # Note: Exclude no states, use SP for internal operation
        address_data = generate_random_address(only_sort_from_states=["SP"])

        # Generate random client data (Company/PJ) - Use NonTaxpayer to avoid IE validation issues
        client_data = generate_random_client_cnpj(
            icms_taxpayer_type="NonTaxpayer", state=address_data["state"]
        )

        # Get serial number for invoice items from stored class variable
        serial = self.test_serial_numbers[0]
        invoice_items = [{"serial_number": serial["serial_no"]}]
        try:
            # Create invoice
            result = create_test_invoice_with_token(
                client_type=client_data["client_type"],
                freight_modality="0 - Freight Contracted by Sender (CIF)",
                operation_type="Outgoing",
                operation_nature="VENDA DE MERCADORIA",
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
                    "Carrier", {"fantasy_name": "Transportadora API Test"}, "name"
                ),
                additional_information="Real API Test Invoice 1 - Internal SP operation - Will remain as Issued",
                total_freight=totals_data["total_freight"],
                total_discount=totals_data["total_discount"],
                total_insurance=totals_data["total_insurance"],
                other_expenses=totals_data["other_expenses"],
                invoice_items_table=invoice_items,
            )

            self.assertTrue(
                result.get("success"),
                f"Invoice creation failed: {result.get('message')}",
            )
            invoice_name = result.get("docname")
            self.assertIsNotNone(invoice_name, "Invoice name should not be None")

            # Store for later tests and tracking
            frappe.flags.test_invoice_1 = invoice_name
            test_results["invoice_docnames"].append(invoice_name)

        except Exception as e:
            self.fail(f"Failed to create invoice: {str(e)}")

        invoice_doc = frappe.get_doc("Product Invoice", invoice_name)

        print(f"\n✅ Invoice 1 created: {invoice_doc.name}")
        print(f"  Client: {invoice_doc.client_name}")
        print(f"  Status: {invoice_doc.invoice_status}")
        print(f"  Total: R$ {invoice_doc.total}")

        # Issue invoice via API (this should populate invoice_id field)
        try:
            # Call the move_to_processing function that submits to NFe.io API
            result = move_invoice_to_processing(invoice_name)

            invoice_doc.reload()

            # Verify result was successful
            self.assertTrue(
                result.get("success"), f"API submission failed: {result.get('message')}"
            )

            # Verify invoice_id is populated
            self.assertIsNotNone(
                invoice_doc.invoice_id,
                "Invoice ID should be populated after moving to processing status",
            )

            print(f"  Invoice ID: {invoice_doc.invoice_id}")
            print(f"  Status after submission: {invoice_doc.invoice_status}")

        except Exception as e:
            self.fail(f"Failed to submit the invoice to processing API: {str(e)}")

        try:
            result = check_invoice_processing(invoice_doc)
            if result["error"]:
                TestProductInvoiceRealAPI.invoice_1_error = True
                self.fail(f"Invoice has Error status: {result['reason']}")

            # Verify invoice fields are populated
            self.assertIsNotNone(
                getattr(invoice_doc, "invoice_access_key", None),
                "Invoice access key should be set",
            )
            self.assertIsNotNone(
                getattr(invoice_doc, "invoice_number", None),
                "Invoice number should be set",
            )
            self.assertIsNotNone(
                getattr(invoice_doc, "invoice_serie", None),
                "Invoice serie should be set",
            )
            self.assertIsNotNone(
                getattr(invoice_doc, "invoice_pdf_url", None),
                "Invoice PDF link should be set",
            )
            self.assertIsNotNone(
                invoice_doc.process_events,
                "Sefaz events should be populated after invoice is confirmed issued",
            )
        except Exception as e:
            self.fail(f"Failed to check invoice processing: {str(e)}")


if __name__ == "__main__":
    import unittest

    unittest.main()
