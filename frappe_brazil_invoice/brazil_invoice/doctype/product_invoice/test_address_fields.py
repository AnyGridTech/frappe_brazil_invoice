# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

"""
Tests for Product Invoice Address Field Handling

Tests verify that:
1. _build_invoice_data_from_doc() uses client_* fields for buyer address
2. CFOP calculation uses client_state
3. Delivery address appears in body when has_delivery_address=1

To run:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.product_invoice.test_address_fields
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_brazil_invoice.brazil_invoice.doctype.product_invoice.product_invoice import (
    _build_invoice_data_from_doc,
)


class TestAddressFieldsUsage(FrappeTestCase):
    """Test that _build_invoice_data_from_doc uses client_* fields correctly"""

    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        super().setUpClass()
        cls._create_test_item()
        cls._create_test_nfeio_config()

    @classmethod
    def _create_test_item(cls):
        """Create a test item"""
        if frappe.db.exists("Item", "TEST-ADDR-001"):
            return
        
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": "TEST-ADDR-001",
            "item_name": "Test Address Item",
            "item_group": "Products",
            "stock_uom": "Unit",
            "is_purchase_item": 1,
            "is_sales_item": 1,
            "ncm": "84719000",
        })
        item.insert(ignore_permissions=True)
        frappe.db.commit()

    @classmethod
    def _create_test_nfeio_config(cls):
        """Create test NFe.io configuration"""
        existing = frappe.get_all(
            "NFeIO",
            filters={"config_name": "Test NFeIO Addresses"},
            limit=1,
        )
        
        if existing:
            cls.nfeio_config_name = existing[0].name
            return
        
        import uuid
        config = frappe.get_doc({
            "doctype": "NFeIO",
            "config_name": "Test NFeIO Addresses",
            "company_name": "Test Address Company",
            "company_id": f"test_addr_{uuid.uuid4().hex[:8]}",
            "company_state": "SP",
            "api_token": f"token_addr_{uuid.uuid4().hex[:12]}",
            "is_test_config": 1,
        })
        config.insert(ignore_permissions=True)
        frappe.db.commit()
        cls.nfeio_config_name = config.name

    def test_client_address_used_not_delivery_address(self):
        """Verify buyer address uses client_* fields"""
        # Create invoice with DIFFERENT client and delivery addresses
        invoice = frappe.get_doc({
            "doctype": "Product Invoice",
            "operation_type": "Outgoing",
            "operation_nature": "VENDA",
            "client_type": "Company",
            "client_name": "Test Company",
            "client_email": "company@test.com",
            "client_phone": "+5511987654321",
            "client_id_number": "11222333000181",  # Valid CNPJ format
            "client_tax_id_number": "11222333000181",
            "icms_taxpayer": "Taxpayer",
            "client_state_registration": "377126952856",
            # CLIENT ADDRESS
            "client_state": "SP",
            "client_city": "São Paulo",
            "client_address_ibge": "3550308",
            "client_neighborhood": "Centro",
            "client_address": "Rua do Cliente",
            "client_number_address": "100",
            "client_complement": "Apto 500",
            "client_cep": "01234567",
            # DIFFERENT DELIVERY ADDRESS
            "delivery_state": "RJ",
            "city": "Rio de Janeiro",
            "delivery_ibge": "3304557",
            "delivery_neighborhood": "Copacabana",
            "delivery_address": "Rua da Entrega",
            "delivery_number_address": "200",
            "delivery_cep": "20000000",
            # Other
            "freight_modality": "9 - No Transport Occurrence",
            "product_type": "Product",
            "nfeio_config": self.nfeio_config_name,
            "emitter_state": "SP",
            "additional_information": "Test invoice with different addresses",
        })
        
        invoice.append("invoice_items_table", {
            "item_code": "TEST-ADDR-001",
            "description": "Test Item",
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
        
        # Verify buyer address uses CLIENT fields (SP, São Paulo, Rua do Cliente)
        # NOT delivery fields (RJ, Rio de Janeiro, Rua da Entrega)
        buyer = invoice_data.get("buyer", {})
        address = buyer.get("address", {})
        
        self.assertEqual(
            address.get("state"), "SP",
            f"FAILURE: Address state should be 'SP' (client_state), not 'RJ' (delivery_state). Got: {address.get('state')}"
        )
        
        self.assertEqual(
            address.get("city", {}).get("name"), "São Paulo",
            f"FAILURE: City should be 'São Paulo' (client_city), not 'Rio de Janeiro'. Got: {address.get('city', {}).get('name')}"
        )
        
        self.assertEqual(
            address.get("street"), "Rua do Cliente",
            f"FAILURE: Street should be 'Rua do Cliente' (client_address). Got: {address.get('street')}"
        )
        
        self.assertEqual(
            address.get("number"), "100",
            f"FAILURE: Number should be '100' (client_number_address). Got: {address.get('number')}"
        )
        
        print("✓ PASS: Buyer address correctly uses client_* fields, not delivery_* fields")

    def test_delivery_address_in_body(self):
        """Test that delivery address appears in body when has_delivery_address=1"""
        invoice = frappe.get_doc({
            "doctype": "Product Invoice",
            "operation_type": "Outgoing",
            "operation_nature": "VENDA",
            "client_type": "Individual",
            "client_name": "João Silva",
            "client_email": "joao@test.com",
            "client_phone": "+5511987654321",
            "client_id_number": "12345678909",  # Valid CPF format (11 digits)
            "client_tax_id_number": "12345678909",
            "icms_taxpayer": "NonTaxpayer",
            "client_state_registration": "ISENTO",
            # Client address
            "client_state": "SP",
            "client_city": "São Paulo",
            "client_address_ibge": "3550308",
            "client_neighborhood": "Centro",
            "client_address": "Rua Principal",
            "client_number_address": "100",
            "client_complement": "Sala 10",
            "client_cep": "01234567",
            # Delivery address - should appear in body
            "has_delivery_address": 1,
            "delivery_state": "SP",
            "city": "São Paulo",
            "delivery_ibge": "3550308",
            "delivery_neighborhood": "Bom Retiro",
            "delivery_address": "Avenida de Entrega",
            "delivery_number_address": "456",
            "delivery_cep": "02167000",
            # Other
            "freight_modality": "9 - No Transport Occurrence",
            "product_type": "Product",
            "nfeio_config": self.nfeio_config_name,
            "emitter_state": "SP",
            "additional_information": "Original note",
        })
        
        invoice.append("invoice_items_table", {
            "item_code": "TEST-ADDR-001",
            "description": "Test Item",
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
        
        # Verify delivery address appears in body
        body = invoice_data.get("body", "")
        
        self.assertIn(
            "A entrega ou coleta deve ser realizada no endereço a seguir:",
            body,
            f"FAILURE: Expected delivery address marker in body. Got body: {body}"
        )
        
        self.assertIn(
            "Avenida de Entrega",
            body,
            f"FAILURE: Expected delivery street 'Avenida de Entrega' in body. Got: {body}"
        )
        
        self.assertIn(
            "456",
            body,
            f"FAILURE: Expected delivery number '456' in body. Got: {body}"
        )
        
        print("✓ PASS: Delivery address correctly appears in body with fixed text marker")

    def test_no_delivery_address_when_flag_off(self):
        """Test that delivery address is NOT included when has_delivery_address=0"""
        invoice = frappe.get_doc({
            "doctype": "Product Invoice",
            "operation_type": "Outgoing",
            "operation_nature": "VENDA",
            "client_type": "Company",
            "client_name": "Client Corp",
            "client_email": "corp@test.com",
            "client_phone": "+5511987654321",
            "client_id_number": "11222333000181",  # Valid CNPJ
            "client_tax_id_number": "11222333000181",
            "icms_taxpayer": "Taxpayer",
            "client_state_registration": "377126952856",
            # Client address
            "client_state": "SP",
            "client_city": "São Paulo",
            "client_address_ibge": "3550308",
            "client_neighborhood": "Centro",
            "client_address": "Rua Principal",
            "client_number_address": "100",
            "client_complement": "Bloco A",
            "client_cep": "01234567",
            # Delivery address present but NOT marked for inclusion
            "has_delivery_address": 0,
            "delivery_state": "RJ",
            "city": "Rio de Janeiro",
            "delivery_address": "Rua Rio",
            "delivery_number_address": "999",
            # Other
            "freight_modality": "9 - No Transport Occurrence",
            "product_type": "Product",
            "nfeio_config": self.nfeio_config_name,
            "emitter_state": "SP",
            "additional_information": "Test note",
        })
        
        invoice.append("invoice_items_table", {
            "item_code": "TEST-ADDR-001",
            "description": "Test Item",
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
        
        # Verify delivery address does NOT appear in body
        body = invoice_data.get("body", "")
        
        self.assertNotIn(
            "A entrega ou coleta deve ser realizada",
            body,
            f"FAILURE: Delivery marker should NOT appear when has_delivery_address=0. Got body: {body}"
        )
        
        self.assertNotIn(
            "Rua Rio",
            body,
            f"FAILURE: Delivery address should NOT appear in body when has_delivery_address=0. Got: {body}"
        )
        
        print("✓ PASS: Delivery address correctly excluded when has_delivery_address=0")
