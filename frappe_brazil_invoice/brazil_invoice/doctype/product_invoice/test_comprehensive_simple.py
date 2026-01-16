# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

"""
Simple Comprehensive Tests for Product Invoice Address Fields

Tests verify that:
1. Client address fields (client_*) are used for buyer address in NFe.io
2. Delivery address appears in additional_information when set
3. CFOP calculation uses client_state not delivery_state

To run these tests:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.product_invoice.test_comprehensive_simple
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_brazil_invoice.brazil_invoice.doctype.product_invoice.product_invoice import (
    _build_invoice_data_from_doc,
)


class TestProductInvoiceAddressFields(FrappeTestCase):
    """Tests for Product Invoice address field handling"""

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests"""
        super().setUpClass()
        cls.nfeio_config = cls._create_test_nfeio_config()
        cls._create_test_item()

    @classmethod
    def _create_test_nfeio_config(cls):
        """Create test NFe.io configuration"""
        existing = frappe.get_all(
            "NFeIO",
            filters={"config_name": "Test NFeIO Simple", "is_test_config": 1},
            limit=1,
        )
        
        if existing:
            return existing[0].name
        
        # Use unique API token for this config
        import uuid
        unique_token = f"test_token_{uuid.uuid4().hex[:12]}"
        
        config = frappe.get_doc({
            "doctype": "NFeIO",
            "config_name": "Test NFeIO Simple",
            "company_name": "Test Company Ltd",
            "company_id": f"test_company_{uuid.uuid4().hex[:8]}",
            "company_state": "SP",
            "api_token": unique_token,
            "is_test_config": 1,
            "usage_priority": 1,
        })
        config.insert(ignore_permissions=True)
        frappe.db.commit()
        return config.name

    @classmethod
    def _create_test_item(cls):
        """Create a test item"""
        if frappe.db.exists("Item", "TEST-PRODUCT-001"):
            return
        
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": "TEST-PRODUCT-001",
            "item_name": "Test Product",
            "item_group": "Products",
            "stock_uom": "Unit",
            "is_purchase_item": 1,
            "is_sales_item": 1,
            "ncm": "84719000",
            "description": "Test product for invoice testing",
        })
        item.insert(ignore_permissions=True)
        frappe.db.commit()

    def setUp(self):
        """Set up each test"""
        frappe.set_user("Administrator")

    def test_01_client_address_used_not_delivery(self):
        """Test that buyer address uses client_* fields, not delivery_* fields"""
        # Create invoice with DIFFERENT client and delivery addresses
        invoice = frappe.get_doc({
            "doctype": "Product Invoice",
            "operation_type": "Outgoing",
            "operation_nature": "VENDA",
            "client_type": "Company",
            "client_name": "Test Client Ltd",
            "client_email": "client@test.com",
            "client_phone": "+55-11987654321",
            "client_id_number": "12345678901234",
            "icms_taxpayer": "Taxpayer",
            "client_state_registration": "377126952856",
            # CLIENT ADDRESS (should be used)
            "client_state": "SP",
            "client_city": "São Paulo",
            "client_address_ibge": "3550308",
            "client_neighborhood": "Centro",
            "client_address": "Rua do Cliente",
            "client_number_address": "100",
            "client_complement": "Sala 101",
            "client_cep": "01234567",
            # DELIVERY ADDRESS (should NOT be used for buyer)
            "delivery_state": "RJ",
            "city": "Rio de Janeiro",
            "delivery_ibge": "3304557",
            "delivery_neighborhood": "Copacabana",
            "delivery_address": "Rua da Entrega",
            "delivery_number_address": "200",
            "delivery_complement": "Apto 201",
            "delivery_cep": "20020000",
            # Other required fields
            "freight_modality": "9 - No Transport Occurrence",
            "product_type": "Product",
            "nfeio_config": self.nfeio_config,
            "is_test_invoice": 1,
            "additional_information": "Test invoice 01",
        })
        
        # Add at least one item
        invoice.append("invoice_items_table", {
            "item_code": "TEST-PRODUCT-001",
            "description": "Test Product",
            "ncm": "84719000",
            "quantity": 1,
            "rate": 100.00,
            "amount": 100.00,
            "unit": "Unit",
            "cfop": "5102",  # Manual CFOP
        })
        
        invoice.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Build invoice data (this is what gets sent to NFe.io)
        invoice_data = _build_invoice_data_from_doc(invoice)
        
        # Verify buyer address uses CLIENT fields, NOT delivery fields
        buyer = invoice_data.get("buyer", {})
        address = buyer.get("address", {})
        
        # Must use CLIENT_STATE not DELIVERY_STATE
        self.assertEqual(
            address.get("state"), "SP",
            f"Expected state='SP' (from client_state), but got '{address.get('state')}' (delivery_state='RJ')"
        )
        
        # Must use CLIENT_CITY not DELIVERY_CITY
        self.assertEqual(
            address.get("city", {}).get("name"), "São Paulo",
            f"Expected city='São Paulo' (from client_city), but got '{address.get('city', {}).get('name')}' (delivery_city='Rio de Janeiro')"
        )
        
        # Must use CLIENT_ADDRESS
        self.assertEqual(
            address.get("street"), "Rua do Cliente",
            f"Expected street='Rua do Cliente' (from client_address), but got '{address.get('street')}'"
        )
        
        # Must use CLIENT_NUMBER_ADDRESS
        self.assertEqual(
            address.get("number"), "100",
            f"Expected number='100' (from client_number_address), but got '{address.get('number')}'"
        )

    def test_02_delivery_address_in_additional_info(self):
        """Test that delivery address appears in additional_information with fixed text"""
        invoice = frappe.get_doc({
            "doctype": "Product Invoice",
            "operation_type": "Outgoing",
            "operation_nature": "VENDA",
            "client_type": "Individual",
            "client_name": "João Silva",
            "client_email": "joao@test.com",
            "client_phone": "+55-11987654321",
            "client_id_number": "12345678901",
            "icms_taxpayer": "NonTaxpayer",
            "client_state_registration": "ISENTO",
            # Client address
            "client_state": "SP",
            "client_city": "São Paulo",
            "client_address_ibge": "3550308",
            "client_neighborhood": "Centro",
            "client_address": "Rua do Cliente",
            "client_number_address": "100",
            "client_cep": "01234567",
            # Delivery address
            "has_delivery_address": 1,
            "delivery_state": "SP",
            "city": "São Paulo",
            "delivery_ibge": "3550308",
            "delivery_neighborhood": "Bom Retiro",
            "delivery_address": "Rua de Entrega",
            "delivery_number_address": "456",
            "delivery_complement": "Apto 201",
            "delivery_cep": "02167000",
            # Other
            "freight_modality": "9 - No Transport Occurrence",
            "product_type": "Product",
            "nfeio_config": self.nfeio_config,
            "is_test_invoice": 1,
            "additional_information": "Original note",
        })
        
        invoice.append("invoice_items_table", {
            "item_code": "TEST-PRODUCT-001",
            "description": "Test Product",
            "ncm": "84719000",
            "quantity": 1,
            "rate": 100.00,
            "amount": 100.00,
            "unit": "Unit",
            "cfop": "5102",
        })
        
        invoice.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Build invoice data
        invoice_data = _build_invoice_data_from_doc(invoice)
        
        # Check body/additional_information contains delivery address info
        body = invoice_data.get("body", "")
        
        # Must contain fixed text marker
        self.assertIn(
            "A entrega ou coleta deve ser realizada no endereço a seguir:",
            body,
            f"Expected delivery address marker in body, but got: {body}"
        )
        
        # Must contain delivery address details
        self.assertIn("Rua de Entrega", body, "Expected delivery street name in body")
        self.assertIn("456", body, "Expected delivery address number in body")

    def test_03_no_delivery_address_when_flag_not_set(self):
        """Test that delivery address is NOT included when has_delivery_address=0"""
        invoice = frappe.get_doc({
            "doctype": "Product Invoice",
            "operation_type": "Outgoing",
            "operation_nature": "VENDA",
            "client_type": "Company",
            "client_name": "Test Company",
            "client_email": "company@test.com",
            "client_phone": "+55-11987654321",
            "client_id_number": "12345678901234",
            "icms_taxpayer": "Taxpayer",
            "client_state_registration": "377126952856",
            # Client address
            "client_state": "SP",
            "client_city": "São Paulo",
            "client_address_ibge": "3550308",
            "client_neighborhood": "Centro",
            "client_address": "Rua Principal",
            "client_number_address": "100",
            "client_cep": "01234567",
            # Delivery address present but not included
            "has_delivery_address": 0,
            "delivery_state": "RJ",
            "city": "Rio de Janeiro",
            "delivery_address": "Rua do Rio",
            "delivery_number_address": "999",
            # Other
            "freight_modality": "9 - No Transport Occurrence",
            "product_type": "Product",
            "nfeio_config": self.nfeio_config,
            "is_test_invoice": 1,
            "additional_information": "Test note",
        })
        
        invoice.append("invoice_items_table", {
            "item_code": "TEST-PRODUCT-001",
            "description": "Test Product",
            "ncm": "84719000",
            "quantity": 1,
            "rate": 100.00,
            "amount": 100.00,
            "unit": "Unit",
            "cfop": "5102",
        })
        
        invoice.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Build invoice data
        invoice_data = _build_invoice_data_from_doc(invoice)
        
        # Delivery address should NOT appear in body
        body = invoice_data.get("body", "")
        
        # Should NOT contain the delivery address marker
        self.assertNotIn(
            "A entrega ou coleta deve ser realizada",
            body,
            f"Delivery address marker should not appear when has_delivery_address=0, but got: {body}"
        )
        
        # Should NOT contain the delivery street
        self.assertNotIn(
            "Rua do Rio",
            body,
            f"Delivery address should not appear in body when has_delivery_address=0"
        )

    def test_04_cfop_calculation_uses_client_state(self):
        """Test that CFOP intrastate/interstate is determined by client_state not delivery_state"""
        # Company in SP (same as nfeio_config.company_state)
        invoice = frappe.get_doc({
            "doctype": "Product Invoice",
            "operation_type": "Outgoing",
            "operation_nature": "VENDA",
            "client_type": "Company",
            "client_name": "Client in SP",
            "client_email": "sp@test.com",
            "client_phone": "+55-11987654321",
            "client_id_number": "11111111111111",
            "icms_taxpayer": "Taxpayer",
            "client_state_registration": "111111111111",
            # Client in SP (same state)
            "client_state": "SP",
            "client_city": "São Paulo",
            "client_address_ibge": "3550308",
            "client_neighborhood": "Centro",
            "client_address": "Rua SP",
            "client_number_address": "100",
            "client_cep": "01234567",
            # But delivery to RJ
            "delivery_state": "RJ",
            "city": "Rio de Janeiro",
            "delivery_neighborhood": "Copacabana",
            "delivery_address": "Rua RJ",
            "delivery_number_address": "200",
            # Other
            "freight_modality": "9 - No Transport Occurrence",
            "product_type": "Product",
            "nfeio_config": self.nfeio_config,
            "is_test_invoice": 1,
        })
        
        invoice.append("invoice_items_table", {
            "item_code": "TEST-PRODUCT-001",
            "description": "Test Product",
            "ncm": "84719000",
            "quantity": 1,
            "rate": 100.00,
            "amount": 100.00,
            "unit": "Unit",
            # Use intrastate CFOP for SP-to-SP
            "cfop": "5102",
        })
        
        invoice.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Build invoice data
        invoice_data = _build_invoice_data_from_doc(invoice)
        
        # Should use intrastate CFOP because client_state==company_state
        # (not because delivery_state==company_state, which would be false)
        self.assertEqual(
            invoice_data.get("cfop"), "5102",
            "CFOP should be intrastate (5102) because client is in SP and company is in SP"
        )


class TestProductInvoiceInterstateOperations(FrappeTestCase):
    """Tests for interstate (different state) operations"""

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests"""
        super().setUpClass()
        cls.nfeio_config = cls._create_test_nfeio_config()
        cls._create_test_item()

    @classmethod
    def _create_test_nfeio_config(cls):
        """Create test NFe.io configuration"""
        existing = frappe.get_all(
            "NFeIO",
            filters={"config_name": "Test NFeIO Interstate", "is_test_config": 1},
            limit=1,
        )
        
        if existing:
            return existing[0].name
        
        # Use unique API token for this config
        import uuid
        unique_token = f"test_token_interstate_{uuid.uuid4().hex[:8]}"
        
        config = frappe.get_doc({
            "doctype": "NFeIO",
            "config_name": "Test NFeIO Interstate",
            "company_name": "Test Company Ltd",
            "company_id": f"test_company_interstate_{uuid.uuid4().hex[:8]}",
            "company_state": "SP",
            "api_token": unique_token,
            "is_test_config": 1,
            "usage_priority": 2,
        })
        config.insert(ignore_permissions=True)
        frappe.db.commit()
        return config.name

    @classmethod
    def _create_test_item(cls):
        """Create a test item"""
        if frappe.db.exists("Item", "TEST-INTERSTATE-001"):
            return
        
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": "TEST-INTERSTATE-001",
            "item_name": "Interstate Test Product",
            "item_group": "Products",
            "stock_uom": "Unit",
            "is_purchase_item": 1,
            "is_sales_item": 1,
            "ncm": "84719000",
        })
        item.insert(ignore_permissions=True)
        frappe.db.commit()

    def setUp(self):
        """Set up each test"""
        frappe.set_user("Administrator")

    def test_interstate_operation_sp_to_rj(self):
        """Test interstate operation (SP company to RJ client)"""
        invoice = frappe.get_doc({
            "doctype": "Product Invoice",
            "operation_type": "Outgoing",
            "operation_nature": "VENDA",
            "client_type": "Company",
            "client_name": "Client in RJ",
            "client_email": "rj@test.com",
            "client_phone": "+55-21987654321",
            "client_id_number": "22222222222222",
            "icms_taxpayer": "Taxpayer",
            "client_state_registration": "222222222222",
            # Client in RJ (different state)
            "client_state": "RJ",
            "client_city": "Rio de Janeiro",
            "client_address_ibge": "3304557",
            "client_neighborhood": "Centro",
            "client_address": "Avenida Rio",
            "client_number_address": "1000",
            "client_cep": "20040020",
            # Other
            "freight_modality": "9 - No Transport Occurrence",
            "product_type": "Product",
            "nfeio_config": self.nfeio_config,
            "is_test_invoice": 1,
        })
        
        invoice.append("invoice_items_table", {
            "item_code": "TEST-INTERSTATE-001",
            "description": "Interstate Product",
            "ncm": "84719000",
            "quantity": 1,
            "rate": 150.00,
            "amount": 150.00,
            "unit": "Unit",
            # Use interstate CFOP for different state
            "cfop": "6102",
        })
        
        invoice.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Build invoice data
        invoice_data = _build_invoice_data_from_doc(invoice)
        
        # Verify client state is RJ (not SP)
        buyer = invoice_data.get("buyer", {})
        self.assertEqual(
            buyer.get("address", {}).get("state"), "RJ",
            "Client state should be RJ for interstate operation"
        )
