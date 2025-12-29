# Copyright (c) 2025, AnyGridTech and Contributors
# See license.txt

"""
Invoice Tests (Mocked)

To run these tests:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.product_invoice.test_product_invoice_mocked

To run a specific test class:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.product_invoice.test_product_invoice_mocked --test TestInvoiceAPI

To run a specific test method:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.product_invoice.test_product_invoice_mocked --test TestInvoiceAPI.test_create_invoice_success
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from datetime import datetime
from unittest.mock import patch


# Import shared test helpers
from . import (
    get_test_run_token,
    create_test_invoice_with_token,
    cleanup_test_invoices,
    create_test_item,
    create_test_serial_no,
    generate_random_client,
    generate_random_totals,
    generate_random_address,
    items_array,
    get_serial_no_array,
    tax_array,
    test_carriers,
    print_invoice_details,
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
    "invoices_created": 0,
    "start_time": None,
    "end_time": None
}


def setUpModule():
    """Set up test data once for the entire module"""
    test_results["start_time"] = datetime.now()
    print("\\nSetting up Product Invoice Mocked test module")


def tearDownModule():
    """Clean up test data after all tests in the module"""
    test_results["end_time"] = datetime.now()
    print("\\nTearing down Product Invoice Mocked test module")
    print_test_dashboard()


def print_test_dashboard():
    """Print a formatted dashboard with test results"""
    width = 80
    
    print("\\n" + "=" * width)
    print("PRODUCT INVOICE MOCKED TEST DASHBOARD".center(width))
    print("=" * width)
    
    # Time information
    if test_results["start_time"] and test_results["end_time"]:
        duration = test_results["end_time"] - test_results["start_time"]
        print(f"\\n⏱  Duration: {duration.total_seconds():.2f}s")
    
    # Test summary
    print("\\n📊 TEST SUMMARY")
    print(f"   Total Tests:    {test_results['total']}")
    print(f"   ✓ Passed:       {test_results['passed']} ({test_results['passed']/max(test_results['total'],1)*100:.1f}%)")
    print(f"   ✗ Failed:       {test_results['failed']}")
    print(f"   ⊘ Skipped:      {test_results['skipped']}")
    
    # Invoice information
    if test_results["invoices_created"] > 0:
        print(f"\\n📄 INVOICES CREATED: {test_results['invoices_created']}")
    
    # Error details
    if test_results["errors"]:
        print("\\n⚠  ERRORS & WARNINGS")
        for error in test_results["errors"][:5]:  # Show max 5 errors
            print(f"   • {error}")
        if len(test_results["errors"]) > 5:
            print(f"   ... and {len(test_results['errors']) - 5} more")
    
    # Status interpretation
    print("\\n💡 TEST ENVIRONMENT NOTES")
    print("   • Tests use mocked NFe.io API responses")
    print("   • No real API calls are made")
    print("   • Tests validate invoice creation and calculation logic")
    
    print("\\n" + "=" * width)
    print()

# =============================================================================
# Cleanup Test - Runs First
# =============================================================================


class TestInvoice000Cleanup(FrappeTestCase):
    """Cleanup test that runs first (alphabetically) to clear old test data"""

    def test_000_cleanup_old_invoices(self):
        """Delete all existing test invoices before test run starts

        Only deletes invoices that have a test token marker in additional_information.
        This ensures real invoices are never accidentally deleted.
        """
        frappe.set_user("Administrator")
        cleanup_test_invoices()


def create_mock_nfeio_response(invoice_total, items_count=1):
    """Create a mock NFe.io API response for tax calculation
    
    Based on NFe.io API documentation:
    https://nfe.io/docs/desenvolvedores/rest-api/calculo-de-impostos-v1/calcula-os-impostos-de-uma-operacao/
    
    Args:
        invoice_total: Total value of the invoice
        items_count: Number of items in the invoice
    
    Returns:
        dict: Mock API response with calculated tax values
    """
    # Calculate mock tax values (using typical Brazilian tax rates)
    # Distribute the total across items
    item_value = invoice_total / items_count
    
    icms_rate = 18.0  # Typical ICMS rate for São Paulo
    icms_value_per_item = item_value * (icms_rate / 100)
    
    ipi_rate = 10.0  # Typical IPI rate for electronics
    ipi_value_per_item = item_value * (ipi_rate / 100)
    
    pis_rate = 1.65  # Standard PIS rate
    pis_value_per_item = item_value * (pis_rate / 100)
    
    cofins_rate = 7.6  # Standard COFINS rate
    cofins_value_per_item = item_value * (cofins_rate / 100)
    
    # Build items array - the API returns taxes per item
    items = []
    for i in range(items_count):
        items.append({
            "itemId": str(i + 1),
            "icms": {
                "pICMS": icms_rate,
                "vBC": round(item_value, 2),
                "vICMS": round(icms_value_per_item, 2)
            },
            "ipi": {
                "pIPI": ipi_rate,
                "vBC": round(item_value, 2),
                "vIPI": round(ipi_value_per_item, 2)
            },
            "pis": {
                "pPIS": pis_rate,
                "vBC": round(item_value, 2),
                "vPIS": round(pis_value_per_item, 2)
            },
            "cofins": {
                "pCOFINS": cofins_rate,
                "vBC": round(item_value, 2),
                "vCOFINS": round(cofins_value_per_item, 2)
            }
        })
    
    return {
        "status": "success",
        "items": items
    }


# =============================================================================
# Mocked API Response Helper
# =============================================================================


class TestInvoiceCreationWithTaxCalculation(FrappeTestCase):
    """Test invoice creation with automatic tax calculation using mocked API"""

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests in this class"""
        frappe.set_user("Administrator")

        # Create test items
        for item_data in items_array:
            create_test_item(
                item_code=item_data["item_code"],
                item_name=item_data["item_name"],
                rate=item_data["rate"],
                ncm_code=item_data["ncm_code"],
                description=item_data["description"],
            )

        # Create test serial numbers using fresh generated serial numbers
        for serial_data in get_serial_no_array():
            create_test_serial_no(
                item_code=serial_data["item_code"], serial_no=serial_data["serial_no"]
            )

        # Create tax templates
        for tax_data in tax_array:
            if not frappe.db.exists(
                "Tax", {"template_name": tax_data["template_name"]}
            ):
                tax_doc = frappe.get_doc({"doctype": "Tax", **tax_data})
                tax_doc.insert(ignore_permissions=True)

        # Create test carriers
        for carrier_data in test_carriers:
            if not frappe.db.exists(
                "Carrier", {"fantasy_name": carrier_data["fantasy_name"]}
            ):
                carrier_doc = frappe.get_doc({"doctype": "Carrier", **carrier_data})
                carrier_doc.insert(ignore_permissions=True)

        frappe.db.commit()

    def setUp(self):
        """Set up each test and track execution"""
        frappe.set_user("Administrator")
        test_results["total"] += 1

    def tearDown(self):
        """Track test results after each test"""
        # Check test outcome
        if hasattr(self, '_outcome'):
            result = self._outcome.result
            
            # Check for failures first
            if result.failures and any(test == self for test, _ in result.failures):
                test_results["failed"] += 1
                failure_info = next((traceback for test, traceback in result.failures if test == self), "Unknown failure")
                error_msg = str(failure_info).split('\n')[-1][:150]
                test_results["errors"].append(f"{self._testMethodName}: {error_msg}")
            # Then check for errors
            elif result.errors and any(test == self for test, _ in result.errors):
                test_results["failed"] += 1
                error_info = next((traceback for test, traceback in result.errors if test == self), "Unknown error")
                error_msg = str(error_info).split('\n')[-1][:150]
                test_results["errors"].append(f"{self._testMethodName}: {error_msg}")
            # Then check for skipped
            elif result.skipped and any(test == self for test, _ in result.skipped):
                test_results["skipped"] += 1
            # Otherwise it passed
            else:
                test_results["passed"] += 1

    def test_create_invoice_with_automatic_tax_calculation(self):
        """Test creating an invoice with automatic ICMS and IPI calculation (mocked)"""
        frappe.set_user("Administrator")

        # Get test item and serial number
        item = items_array[0]
        serial = get_serial_no_array()[0]

        # Prepare invoice items
        invoice_items = [{"serial_number": serial["serial_no"]}]

        # Generate random client data (Company/PJ)
        client_data = generate_random_client(client_type="Company")

        # Generate random address data
        address_data = generate_random_address()

        # Generate random totals
        totals_data = generate_random_totals()

        # Mock the NFe.io API response
        with patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.tax._call_nfeio_api') as mock_api:
            # Calculate expected total for mock response
            invoice_total = item["rate"] + totals_data["total_freight"] + totals_data["total_insurance"] + totals_data["other_expenses"] - totals_data["total_discount"]
            mock_api.return_value = create_mock_nfeio_response(invoice_total)

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
                additional_information="Test invoice for automatic ICMS and IPI calculation (mocked)",
                total_freight=totals_data["total_freight"],
                total_discount=totals_data["total_discount"],
                total_insurance=totals_data["total_insurance"],
                other_expenses=totals_data["other_expenses"],
                tax_template=frappe.db.get_value(
                    "Tax", {"template_name": "Remessa em Garantia"}, "name"
                ),
                invoice_items_table=invoice_items,
            )

            # Verify invoice was created successfully
            self.assertTrue(
                result.get("success"), f"Invoice creation failed: {result.get('message')}"
            )
            invoice_name = result.get("docname")
            self.assertIsNotNone(invoice_name, "Invoice name should not be None")
            
            # Track invoice creation
            test_results["invoices_created"] += 1

            # Fetch the created invoice
            invoice = frappe.get_doc("Product Invoice", invoice_name)

            # Verify basic fields
            self.assertEqual(invoice.client_name, client_data["client_name"])
            self.assertEqual(invoice.product_brand, "Growatt")

            # Verify ICMS and IPI were calculated
            self.assertIsNotNone(invoice.icms_value, "ICMS value should be calculated")
            self.assertGreater(invoice.icms_value, 0, "ICMS value should be greater than 0")
            self.assertIsNotNone(invoice.ipi_value, "IPI value should be calculated")
            self.assertGreater(invoice.ipi_value, 0, "IPI value should be greater than 0")

            # Display invoice details
            print_invoice_details(invoice, show_items=False)
            print("✅ Tax values calculated successfully using mocked NFe.io API")
            print(f"  ICMS: R$ {invoice.icms_value:.2f}, IPI: R$ {invoice.ipi_value:.2f}")


if __name__ == "__main__":
    import unittest
    unittest.main()
