# Copyright (c) 2025, AnyGridTech and Contributors
# See license.txt

"""
Invoice Tests

To run these tests:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.invoices.test_invoices

To run a specific test class:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.invoices.test_invoices --test TestInvoiceAPI

To run a specific test method:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.invoices.test_invoices --test TestInvoiceAPI.test_create_invoice_success
"""

import frappe
import unittest
import json
from frappe.tests.utils import FrappeTestCase
from frappe_brazil_invoice.brazil_invoice.doctype.invoices.invoices import (
    create_invoice,
    get_invoice_details,
    update_invoice_status,
    bulk_create_invoices,
    bulk_process_invoices
)


class TestInvoices(FrappeTestCase):
	"""Test cases for Invoice doctype"""
	pass


# =============================================================================
# Invoice API Tests
# =============================================================================

class TestInvoiceAPI(unittest.TestCase):
    """Test cases for Invoice API endpoints"""

    def setUp(self):
        """Set up test data before each test"""
        frappe.set_user("Administrator")

    def tearDown(self):
        """Clean up after each test"""
        frappe.db.rollback()

    def test_create_invoice_success(self):
        """Test successful invoice creation with minimal required fields"""
        result = create_invoice(
            client_name="Test Client",
            client_id_number="12345678901"
        )

        # Print result for debugging if test fails
        if not result.get("success"):
            print(f"Result: {result}")
        
        self.assertTrue(result.get("success"), f"Failed: {result.get('message')}")
        self.assertIsNotNone(result.get("docname"))
        self.assertIn("created successfully", result.get("message"))
        
        # Verify invoice is in draft state
        docname = result.get("docname")
        invoice = frappe.get_doc("Invoices", docname)
        self.assertEqual(invoice.docstatus, 0)  # 0 = Draft

    def test_create_invoice_with_all_fields(self):
        """Test invoice creation with all fields populated"""
        result = create_invoice(
            client_name="Complete Test Client",
            client_id_number="98765432109876",
            client_email="test@example.com",
            client_phone="+55 11 98765-4321",
            contribuinte_icms="Contribuinte",
            inscricao_estadual="123456789",
            operation_type="Remessa para Conserto",
            freight_modality="0 - Contratação do Frete por Conta do Remetente (CIF)",
            delivery_address="Avenida Paulista, 1578",
            delivery_number_address="1578",
            delivery_neighborhood="Bela Vista",
            city="São Paulo",
            delivery_state="SP",
            delivery_cep="01310-100",
            product_brand="Test Brand",
            product_quantity="10",
            product_type="Caixa",
            product_gross_weight="15.5",
            product_net_weight="14.0",
            additional_information="Test invoice",
            total=1500.00,
            total_tax=270.00,
            total_freight=50.00,
            total_discount=10.00,
            invoices_table=[
                {
                    "item_code": "ITEM-001",
                    "description": "Test Product 1",
                    "quantity": 1,
                    "unit_price": 1000.00,
                    "total": 1000.00
                },
                {
                    "item_code": "ITEM-002",
                    "description": "Test Product 2",
                    "quantity": 1,
                    "unit_price": 500.00,
                    "total": 500.00
                }
            ]
        )

        # Debug output if test fails
        if not result.get("success"):
            print(f"All fields test failed: {result.get('message')}")
        
        self.assertTrue(result.get("success"), f"Failed: {result.get('message')}")
        self.assertIsNotNone(result.get("docname"))
        
        # Verify the invoice was actually created
        docname = result.get("docname")
        self.assertTrue(frappe.db.exists("Invoices", docname))
        
        # Verify some field values
        invoice = frappe.get_doc("Invoices", docname)
        self.assertEqual(invoice.client_name, "Complete Test Client")
        self.assertEqual(invoice.client_email, "test@example.com")
        self.assertEqual(invoice.total, 1500.00)
        self.assertEqual(len(invoice.invoices_table), 2)

    def test_create_invoice_missing_required_fields(self):
        """Test invoice creation fails when required fields are missing"""
        # Missing both required fields
        result = create_invoice()
        self.assertFalse(result.get("success"))
        self.assertIn("Missing required fields", result.get("message"))

        # Missing client_id_number
        result = create_invoice(client_name="Test Client")
        self.assertFalse(result.get("success"))
        self.assertIn("client_id_number", result.get("message"))

        # Missing client_name
        result = create_invoice(client_id_number="12345678901")
        self.assertFalse(result.get("success"))
        self.assertIn("client_name", result.get("message"))

    def test_create_invoice_with_json_string_items(self):
        """Test invoice creation with invoices_table as JSON string"""
        items = [
            {
                "item_code": "ITEM-JSON-001",
                "description": "JSON Test Product",
                "quantity": 2,
                "unit_price": 500.00,
                "total": 1000.00
            }
        ]
        
        result = create_invoice(
            client_name="JSON Test Client",
            client_id_number="22222222222",
            invoices_table=json.dumps(items)
        )

        self.assertTrue(result.get("success"))
        
        # Verify the items were added
        docname = result.get("docname")
        invoice = frappe.get_doc("Invoices", docname)
        self.assertEqual(len(invoice.invoices_table), 1)

    def test_get_invoice_details_success(self):
        """Test retrieving invoice details successfully"""
        # First create an invoice
        create_result = create_invoice(
            client_name="Details Test",
            client_id_number="33333333333"
        )
        docname = create_result.get("docname")

        # Then retrieve its details
        result = get_invoice_details(docname)

        self.assertTrue(result.get("success"))
        self.assertIsNotNone(result.get("invoice"))
        self.assertEqual(result.get("invoice").get("name"), docname)
        self.assertEqual(result.get("invoice").get("client_name"), "Details Test")

    def test_get_invoice_details_not_found(self):
        """Test retrieving non-existent invoice"""
        result = get_invoice_details("NON-EXISTENT-INVOICE")

        self.assertFalse(result.get("success"))
        self.assertIn("does not exist", result.get("message"))

    def test_get_invoice_details_missing_docname(self):
        """Test retrieving invoice without providing docname"""
        result = get_invoice_details(None)

        self.assertFalse(result.get("success"))
        self.assertIn("required", result.get("message"))

    def test_update_invoice_status_success(self):
        """Test updating invoice status successfully"""
        # Create an invoice
        create_result = create_invoice(
            client_name="Update Test",
            client_id_number="44444444444"
        )
        docname = create_result.get("docname")

        # Update its status
        result = update_invoice_status(
            docname=docname,
            invoice_id="nfe-test-12345",
            invoice_link="https://example.com/invoice.pdf",
            invoice_number="000123",
            invoice_serie="1"
        )

        self.assertTrue(result.get("success"))
        
        # Verify the update
        invoice = frappe.get_doc("Invoices", docname)
        self.assertEqual(invoice.invoice_id, "nfe-test-12345")
        self.assertEqual(invoice.invoice_link, "https://example.com/invoice.pdf")
        self.assertEqual(invoice.invoice_number, "000123")
        self.assertEqual(invoice.invoice_serie, "1")

    def test_update_invoice_status_not_found(self):
        """Test updating non-existent invoice"""
        result = update_invoice_status(
            docname="NON-EXISTENT",
            invoice_id="test-123"
        )

        self.assertFalse(result.get("success"))
        self.assertIn("does not exist", result.get("message"))

    def test_update_invoice_status_missing_docname(self):
        """Test updating invoice without docname"""
        result = update_invoice_status(docname=None)

        self.assertFalse(result.get("success"))
        self.assertIn("required", result.get("message"))

    def test_bulk_create_invoices_success(self):
        """Test bulk invoice creation with all successful"""
        invoices_data = [
            {
                "client_name": f"Bulk Client {i}",
                "client_id_number": f"5555555555{i}",
                "total": 1000.00 * (i + 1)
            }
            for i in range(3)
        ]

        result = bulk_create_invoices(invoices_data)

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("total_processed"), 3)
        self.assertEqual(result.get("total_success"), 3)
        self.assertEqual(result.get("total_failed"), 0)
        self.assertEqual(len(result.get("created_invoices")), 3)
        self.assertEqual(len(result.get("failed_invoices")), 0)

    def test_bulk_create_invoices_partial_failure(self):
        """Test bulk invoice creation with some failures"""
        invoices_data = [
            {
                "client_name": "Valid Client 1",
                "client_id_number": "66666666661"
            },
            {
                "client_name": "Invalid Client",
                # Missing client_id_number
            },
            {
                "client_name": "Valid Client 2",
                "client_id_number": "66666666663"
            }
        ]

        result = bulk_create_invoices(invoices_data)

        self.assertFalse(result.get("success"))  # Not all succeeded
        self.assertEqual(result.get("total_processed"), 3)
        self.assertEqual(result.get("total_success"), 2)
        self.assertEqual(result.get("total_failed"), 1)
        self.assertEqual(len(result.get("created_invoices")), 2)
        self.assertEqual(len(result.get("failed_invoices")), 1)

    def test_bulk_create_invoices_with_json_string(self):
        """Test bulk creation with JSON string input"""
        invoices_data = [
            {
                "client_name": "JSON Bulk 1",
                "client_id_number": "77777777771"
            },
            {
                "client_name": "JSON Bulk 2",
                "client_id_number": "77777777772"
            }
        ]

        result = bulk_create_invoices(json.dumps(invoices_data))

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("total_success"), 2)

    def test_bulk_create_invoices_invalid_input(self):
        """Test bulk creation with invalid input type"""
        result = bulk_create_invoices("not a list")

        self.assertFalse(result.get("success"))
        self.assertIn("must be a list", result.get("message"))

    def test_bulk_create_invoices_empty_list(self):
        """Test bulk creation with empty list"""
        result = bulk_create_invoices([])

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("total_processed"), 0)
        self.assertEqual(result.get("total_success"), 0)
        self.assertEqual(result.get("total_failed"), 0)

    def test_bulk_process_invoices_invalid_input(self):
        """Test bulk processing with invalid input type"""
        result = bulk_process_invoices("not a list")

        self.assertFalse(result.get("success"))
        self.assertIn("must be a list", result.get("message"))

    def test_bulk_process_invoices_empty_list(self):
        """Test bulk processing with empty list"""
        result = bulk_process_invoices([])

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("total_processed"), 0)
        self.assertEqual(result.get("total_success"), 0)
        self.assertEqual(result.get("total_failed"), 0)

    def test_bulk_process_invoices_nonexistent_invoices(self):
        """Test bulk processing with non-existent invoice docnames"""
        invoice_names = ["NON-EXISTENT-1", "NON-EXISTENT-2"]
        
        result = bulk_process_invoices(invoice_names)

        # All should fail since invoices don't exist
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("total_processed"), 2)
        self.assertEqual(result.get("total_success"), 0)
        self.assertEqual(result.get("total_failed"), 2)
        self.assertEqual(len(result.get("failed_invoices")), 2)

    def test_bulk_process_invoices_with_json_string(self):
        """Test bulk processing with JSON string input"""
        # First create some invoices
        invoice_names = []
        for i in range(2):
            create_result = create_invoice(
                client_name=f"Bulk Process Client {i}",
                client_id_number=f"8888888888{i}"
            )
            if create_result.get("success"):
                # Submit the invoice so it can be processed
                invoice_doc = frappe.get_doc("Invoices", create_result.get("docname"))
                invoice_doc.submit()
                invoice_names.append(create_result.get("docname"))
        
        # Convert to JSON string
        result = bulk_process_invoices(json.dumps(invoice_names))

        # Note: This will fail in test environment without actual NFe.io service
        # but it tests the JSON parsing works correctly
        self.assertIsNotNone(result.get("total_processed"))
        self.assertEqual(result.get("total_processed"), len(invoice_names))


# =============================================================================
# Invoice Tax Tests
# =============================================================================

class TestInvoiceTaxes(unittest.TestCase):
    """Test cases for invoice tax calculations and different tax types"""

    def setUp(self):
        """Set up test data before each test"""
        frappe.set_user("Administrator")

    def tearDown(self):
        """Clean up after each test"""
        frappe.db.rollback()

    def test_invoice_with_icms_tax(self):
        """Test invoice creation with ICMS tax"""
        result = create_invoice(
            client_name="ICMS Test Client",
            client_id_number="11111111111111",
            contribuinte_icms="Contribuinte",
            inscricao_estadual="123456789",
            delivery_state="SP",
            total=1000.00,
            total_tax=180.00,  # 18% ICMS
            additional_information="ICMS 18% aplicado"
        )

        self.assertTrue(result.get("success"))
        
        # Verify tax was set correctly
        docname = result.get("docname")
        invoice = frappe.get_doc("Invoices", docname)
        self.assertEqual(invoice.total_tax, 180.00)
        self.assertEqual(invoice.contribuinte_icms, "Contribuinte")

    def test_invoice_with_iss_tax(self):
        """Test invoice creation with ISS tax (service tax)"""
        result = create_invoice(
            client_name="ISS Test Client",
            client_id_number="22222222222222",
            delivery_state="SP",
            city="São Paulo",
            total=5000.00,
            total_tax=250.00,  # 5% ISS
            additional_information="ISS 5% - Serviços"
        )

        self.assertTrue(result.get("success"))
        
        docname = result.get("docname")
        invoice = frappe.get_doc("Invoices", docname)
        self.assertEqual(invoice.total_tax, 250.00)
        self.assertIn("ISS", invoice.additional_information)

    def test_invoice_with_ipi_tax(self):
        """Test invoice creation with IPI tax (industrial products)"""
        result = create_invoice(
            client_name="IPI Test Client",
            client_id_number="33333333333333",
            total=10000.00,
            total_tax=1500.00,  # IPI 15%
            additional_information="IPI 15% sobre produtos industrializados"
        )

        self.assertTrue(result.get("success"))
        
        docname = result.get("docname")
        invoice = frappe.get_doc("Invoices", docname)
        self.assertEqual(invoice.total_tax, 1500.00)

    def test_invoice_with_pis_cofins_tax(self):
        """Test invoice creation with PIS/COFINS taxes"""
        # PIS (1.65%) + COFINS (7.6%) = 9.25%
        base_value = 20000.00
        pis_rate = 0.0165
        cofins_rate = 0.076
        total_tax = base_value * (pis_rate + cofins_rate)
        
        result = create_invoice(
            client_name="PIS/COFINS Test Client",
            client_id_number="44444444444444",
            total=base_value,
            total_tax=total_tax,
            additional_information=f"PIS 1.65% + COFINS 7.6% = {total_tax:.2f}"
        )

        self.assertTrue(result.get("success"))
        
        docname = result.get("docname")
        invoice = frappe.get_doc("Invoices", docname)
        self.assertEqual(invoice.total_tax, total_tax)

    def test_invoice_with_multiple_taxes(self):
        """Test invoice with multiple tax types combined"""
        base_value = 10000.00
        icms = base_value * 0.18  # 18%
        ipi = base_value * 0.10   # 10%
        pis = base_value * 0.0165 # 1.65%
        cofins = base_value * 0.076  # 7.6%
        total_tax = icms + ipi + pis + cofins
        
        result = create_invoice(
            client_name="Multiple Taxes Client",
            client_id_number="55555555555555",
            contribuinte_icms="Contribuinte",
            inscricao_estadual="987654321",
            delivery_state="SP",
            total=base_value,
            total_tax=total_tax,
            additional_information=f"ICMS: {icms}, IPI: {ipi}, PIS: {pis}, COFINS: {cofins}"
        )

        self.assertTrue(result.get("success"))
        
        docname = result.get("docname")
        invoice = frappe.get_doc("Invoices", docname)
        self.assertEqual(invoice.total_tax, total_tax)

    def test_invoice_tax_exempt(self):
        """Test invoice for tax-exempt transactions"""
        result = create_invoice(
            client_name="Tax Exempt Client",
            client_id_number="66666666666666",
            contribuinte_icms="Contribuinte Isento",
            total=8000.00,
            total_tax=0.00,
            additional_information="Isento de impostos conforme lei XYZ"
        )

        self.assertTrue(result.get("success"))
        
        docname = result.get("docname")
        invoice = frappe.get_doc("Invoices", docname)
        self.assertEqual(invoice.total_tax, 0.00)
        self.assertEqual(invoice.contribuinte_icms, "Contribuinte Isento")

    def test_invoice_with_tax_template(self):
        """Test invoice using tax template field (without template validation)"""
        # Test that tax_template field can be set
        # Note: This tests the field is accepted, not actual template validation
        result = create_invoice(
            client_name="Tax Template Client",
            client_id_number="77777777777777",
            total=15000.00,
            total_tax=2700.00,
            additional_information="Impostos aplicados via template"
        )

        self.assertTrue(result.get("success"), f"Failed: {result.get('message')}")
        
        if result.get("success"):
            docname = result.get("docname")
            invoice = frappe.get_doc("Invoices", docname)
            self.assertEqual(invoice.total_tax, 2700.00)
            # Verify the tax_template field exists in the doctype
            self.assertTrue(hasattr(invoice, 'tax_template'))

    def test_interstate_icms_different_rates(self):
        """Test ICMS with different interstate rates"""
        # Interstate ICMS typically has different rates (7% or 12%)
        test_cases = [
            ("SP", "RJ", 12.0),  # SP to RJ - 12%
            ("SP", "BA", 7.0),   # SP to BA - 7%
        ]
        
        for origin, destination, rate in test_cases:
            base_value = 5000.00
            tax_value = base_value * (rate / 100)
            
            result = create_invoice(
                client_name=f"Interstate Test {origin}-{destination}",
                client_id_number=f"888888888888{rate:.0f}",
                contribuinte_icms="Contribuinte",
                delivery_state=destination,
                total=base_value,
                total_tax=tax_value,
                additional_information=f"ICMS Interestadual {origin} → {destination}: {rate}%"
            )
            
            self.assertTrue(result.get("success"))
            
            docname = result.get("docname")
            invoice = frappe.get_doc("Invoices", docname)
            self.assertEqual(invoice.delivery_state, destination)
            self.assertAlmostEqual(float(invoice.total_tax), tax_value, places=2)

    def test_invoice_with_tax_and_freight(self):
        """Test invoice with taxes calculated including freight"""
        product_value = 10000.00
        freight_value = 500.00
        base_for_tax = product_value + freight_value
        tax_rate = 0.18  # 18% ICMS
        tax_value = base_for_tax * tax_rate
        
        result = create_invoice(
            client_name="Tax on Freight Client",
            client_id_number="99999999999999",
            contribuinte_icms="Contribuinte",
            total=product_value,
            total_freight=freight_value,
            total_tax=tax_value,
            additional_information=f"ICMS sobre base incluindo frete: {tax_value:.2f}"
        )

        self.assertTrue(result.get("success"))
        
        docname = result.get("docname")
        invoice = frappe.get_doc("Invoices", docname)
        self.assertAlmostEqual(float(invoice.total_freight), freight_value, places=2)
        self.assertAlmostEqual(float(invoice.total_tax), tax_value, places=2)

    def test_invoice_simples_nacional(self):
        """Test invoice for Simples Nacional taxpayers (simplified tax regime)"""
        # Simples Nacional has unified tax rates
        result = create_invoice(
            client_name="Simples Nacional Client",
            client_id_number="10101010101010",
            contribuinte_icms="Não Contribuinte",
            total=7000.00,
            total_tax=420.00,  # 6% unified rate
            additional_information="Simples Nacional - Alíquota única 6%"
        )

        self.assertTrue(result.get("success"))
        
        docname = result.get("docname")
        invoice = frappe.get_doc("Invoices", docname)
        self.assertEqual(invoice.contribuinte_icms, "Não Contribuinte")
        self.assertEqual(invoice.total_tax, 420.00)

    def test_bulk_invoices_with_different_taxes(self):
        """Test bulk creation with different tax scenarios"""
        invoices_data = [
            {
                "client_name": "Bulk ICMS Client",
                "client_id_number": "11111111111",
                "contribuinte_icms": "Contribuinte",
                "total": 1000.00,
                "total_tax": 180.00
            },
            {
                "client_name": "Bulk ISS Client",
                "client_id_number": "22222222222",
                "total": 2000.00,
                "total_tax": 100.00
            },
            {
                "client_name": "Bulk Tax Exempt Client",
                "client_id_number": "33333333333",
                "contribuinte_icms": "Contribuinte Isento",
                "total": 3000.00,
                "total_tax": 0.00
            }
        ]

        result = bulk_create_invoices(invoices_data)

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("total_success"), 3)
        
        # Verify different tax values
        for invoice_info in result.get("created_invoices"):
            invoice = frappe.get_doc("Invoices", invoice_info["docname"])
            self.assertIsNotNone(invoice.total_tax)
