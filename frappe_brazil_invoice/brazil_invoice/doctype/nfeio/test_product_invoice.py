# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

"""
Unit tests for Product Invoice Operations with NFe.io API

Tests cover:
- Issue/emit product invoices
- Cancel product invoices
- Query invoice events
- Retrieve PDF (DANFE)
- Retrieve XML
- API error handling
- Payload building
"""

import json
import unittest
from unittest.mock import Mock, patch
import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_brazil_invoice.brazil_invoice.doctype.nfeio import product_invoice


class TestProductInvoice(FrappeTestCase):
    """Test cases for Product Invoice operations"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock NFe.io configuration
        self.nfeio_config = Mock()
        self.nfeio_config.api_token = "test_api_token_12345"
        self.nfeio_config.company_id = "test_company_123"
        self.nfeio_config.company_name = "Test Company Ltd"
        
        # Sample invoice data
        self.sample_invoice_data = {
            "operationNature": "VENDA",
            "operationType": "Outgoing",
            "consumerType": "FinalConsumer",
            "buyer": {
                "name": "Customer Test",
                "federalTaxNumber": 12345678901234
            },
            "items": [
                {
                    "code": "PROD001",
                    "description": "Test Product",
                    "quantity": 1,
                    "unitAmount": 100.0,
                    "totalAmount": 100.0,
                    "cfop": 5102,
                    "ncm": "12345678"
                }
            ],
            "totals": {
                "icms": {
                    "productAmount": 100.0,
                    "invoiceAmount": 100.0
                }
            }
        }
        
        # Sample API responses
        self.sample_issue_response = {
            "id": "nfe_abc123xyz",
            "status": "Queued",
            "number": 1001
        }
        
        self.sample_events_response = {
            "events": [
                {
                    "id": "evt_123",
                    "type": "Authorized",
                    "createdOn": "2025-12-28T10:00:00Z"
                },
                {
                    "id": "evt_124",
                    "type": "Issued",
                    "createdOn": "2025-12-28T10:01:00Z"
                }
            ],
            "hasMore": False
        }
        
        self.sample_pdf_response = {
            "uri": "https://api.nfse.io/documents/nfe_abc123xyz.pdf"
        }
        
        self.sample_xml_response = {
            "uri": "https://api.nfse.io/documents/nfe_abc123xyz.xml"
        }
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_issue_product_invoice_success(self, mock_requests):
        """Test successful invoice issuance"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.json.return_value = self.sample_issue_response
        mock_response.content = json.dumps(self.sample_issue_response).encode()
        mock_requests.post.return_value = mock_response
        
        # Call function
        result = product_invoice.issue_product_invoice(
            self.sample_invoice_data, 
            self.nfeio_config
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "nfe_abc123xyz")
        self.assertEqual(result["status"], "Queued")
        
        # Verify API was called correctly
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        self.assertIn("/companies/test_company_123/productinvoices", call_args[0][0])
        self.assertEqual(call_args[1]["headers"]["Authorization"], "test_api_token_12345")
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_issue_product_invoice_missing_company_id(self, mock_requests):
        """Test invoice issuance with missing company ID"""
        # Remove company_id
        self.nfeio_config.company_id = None
        
        # Call function and expect error
        with self.assertRaises(product_invoice.NFeIOAPIError) as context:
            product_invoice.issue_product_invoice(
                self.sample_invoice_data, 
                self.nfeio_config
            )
        
        self.assertIn("Company ID not configured", str(context.exception))
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_issue_product_invoice_api_error(self, mock_requests):
        """Test invoice issuance with API error"""
        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid invoice data"
        mock_requests.post.return_value = mock_response
        
        # Call function and expect error
        with self.assertRaises(product_invoice.NFeIOAPIError) as context:
            product_invoice.issue_product_invoice(
                self.sample_invoice_data, 
                self.nfeio_config
            )
        
        self.assertIn("Bad request", str(context.exception))
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_cancel_product_invoice_success(self, mock_requests):
        """Test successful invoice cancellation"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.content = b''
        mock_requests.delete.return_value = mock_response
        
        # Call function
        result = product_invoice.cancel_product_invoice(
            "nfe_abc123xyz", 
            "Customer requested cancellation", 
            self.nfeio_config
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertTrue(result.get("success"))
        
        # Verify API was called correctly
        mock_requests.delete.assert_called_once()
        call_args = mock_requests.delete.call_args
        self.assertIn("/productinvoices/nfe_abc123xyz", call_args[0][0])
        self.assertEqual(
            call_args[1]["params"]["reason"], 
            "Customer requested cancellation"
        )
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_cancel_product_invoice_missing_reason(self, mock_requests):
        """Test invoice cancellation without reason"""
        # Call function and expect error
        with self.assertRaises(product_invoice.NFeIOAPIError) as context:
            product_invoice.cancel_product_invoice(
                "nfe_abc123xyz", 
                "", 
                self.nfeio_config
            )
        
        self.assertIn("reason is required", str(context.exception))
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_cancel_product_invoice_not_found(self, mock_requests):
        """Test cancellation of non-existent invoice"""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Invoice not found"
        mock_requests.delete.return_value = mock_response
        
        # Call function and expect error
        with self.assertRaises(product_invoice.NFeIOAPIError) as context:
            product_invoice.cancel_product_invoice(
                "nfe_nonexistent", 
                "Test cancellation", 
                self.nfeio_config
            )
        
        self.assertIn("not found", str(context.exception))
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_get_invoice_events_success(self, mock_requests):
        """Test successful retrieval of invoice events"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_events_response
        mock_response.content = json.dumps(self.sample_events_response).encode()
        mock_requests.get.return_value = mock_response
        
        # Call function
        result = product_invoice.get_invoice_events(
            "nfe_abc123xyz", 
            self.nfeio_config,
            limit=10,
            starting_after=0
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("events", result)
        self.assertEqual(len(result["events"]), 2)
        self.assertEqual(result["events"][0]["type"], "Authorized")
        self.assertFalse(result["hasMore"])
        
        # Verify API was called correctly
        mock_requests.get.assert_called_once()
        call_args = mock_requests.get.call_args
        self.assertIn("/productinvoices/nfe_abc123xyz/events", call_args[0][0])
        self.assertEqual(call_args[1]["params"]["limit"], 10)
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_get_invoice_events_pagination(self, mock_requests):
        """Test invoice events retrieval with pagination"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "events": [],
            "hasMore": True
        }
        mock_response.content = b'{"events":[],"hasMore":true}'
        mock_requests.get.return_value = mock_response
        
        # Call function with pagination
        product_invoice.get_invoice_events(
            "nfe_abc123xyz", 
            self.nfeio_config,
            limit=20,
            starting_after=10
        )
        
        # Verify pagination parameters
        call_args = mock_requests.get.call_args
        self.assertEqual(call_args[1]["params"]["limit"], 20)
        self.assertEqual(call_args[1]["params"]["startingAfter"], 10)
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_get_invoice_pdf_success(self, mock_requests):
        """Test successful PDF URL retrieval"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_pdf_response
        mock_response.content = json.dumps(self.sample_pdf_response).encode()
        mock_requests.get.return_value = mock_response
        
        # Call function
        result = product_invoice.get_invoice_pdf(
            "nfe_abc123xyz", 
            self.nfeio_config,
            force=False
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("uri", result)
        self.assertTrue(result["uri"].endswith(".pdf"))
        
        # Verify API was called correctly
        mock_requests.get.assert_called_once()
        call_args = mock_requests.get.call_args
        self.assertIn("/productinvoices/nfe_abc123xyz/pdf", call_args[0][0])
        self.assertEqual(call_args[1]["params"]["force"], "false")
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_get_invoice_pdf_with_force(self, mock_requests):
        """Test PDF URL retrieval with force parameter"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_pdf_response
        mock_response.content = json.dumps(self.sample_pdf_response).encode()
        mock_requests.get.return_value = mock_response
        
        # Call function with force=True
        product_invoice.get_invoice_pdf(
            "nfe_abc123xyz", 
            self.nfeio_config,
            force=True
        )
        
        # Verify force parameter
        call_args = mock_requests.get.call_args
        self.assertEqual(call_args[1]["params"]["force"], "true")
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_get_invoice_xml_success(self, mock_requests):
        """Test successful XML URL retrieval"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_xml_response
        mock_response.content = json.dumps(self.sample_xml_response).encode()
        mock_requests.get.return_value = mock_response
        
        # Call function
        result = product_invoice.get_invoice_xml(
            "nfe_abc123xyz", 
            self.nfeio_config
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("uri", result)
        self.assertTrue(result["uri"].endswith(".xml"))
        
        # Verify API was called correctly
        mock_requests.get.assert_called_once()
        call_args = mock_requests.get.call_args
        self.assertIn("/productinvoices/nfe_abc123xyz/xml", call_args[0][0])
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_api_authentication_error(self, mock_requests):
        """Test API authentication failure"""
        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API token"
        mock_requests.get.return_value = mock_response
        
        # Call function and expect error
        with self.assertRaises(product_invoice.NFeIOAPIError) as context:
            product_invoice.get_invoice_xml(
                "nfe_abc123xyz", 
                self.nfeio_config
            )
        
        self.assertIn("Authentication failed", str(context.exception))
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_api_timeout(self, mock_requests):
        """Test API request timeout"""
        # Mock timeout
        import requests
        mock_requests.get.side_effect = requests.exceptions.Timeout()
        
        # Call function and expect error
        with self.assertRaises(product_invoice.NFeIOAPIError) as context:
            product_invoice.get_invoice_xml(
                "nfe_abc123xyz", 
                self.nfeio_config
            )
        
        self.assertIn("timed out", str(context.exception))
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_api_connection_error(self, mock_requests):
        """Test API connection error"""
        # Mock connection error
        import requests
        mock_requests.post.side_effect = requests.exceptions.ConnectionError()
        
        # Call function and expect error
        with self.assertRaises(product_invoice.NFeIOAPIError) as context:
            product_invoice.issue_product_invoice(
                self.sample_invoice_data, 
                self.nfeio_config
            )
        
        self.assertIn("Failed to connect", str(context.exception))
    
    def test_build_invoice_payload_basic(self):
        """Test building invoice payload from document"""
        # Create mock invoice document
        mock_invoice = Mock()
        mock_invoice.get = Mock(side_effect=lambda key, default=None: {
            "operation_nature": "VENDA",
            "customer": "CUST-001",
            "customer_name": "Test Customer",
            "customer_tax_id": "12345678901234",
            "total_amount": 500.0,
            "items": []
        }.get(key, default))
        mock_invoice.items = []
        
        # Build payload
        payload = product_invoice.build_invoice_payload(mock_invoice)
        
        # Assertions
        self.assertIsNotNone(payload)
        self.assertEqual(payload["operationNature"], "VENDA")
        self.assertEqual(payload["operationType"], "Outgoing")
        self.assertIn("buyer", payload)
        self.assertEqual(payload["buyer"]["name"], "Test Customer")
        self.assertIn("items", payload)
        self.assertIn("totals", payload)
    
    def test_build_invoice_payload_with_items(self):
        """Test building invoice payload with line items"""
        # Create mock invoice document with items
        mock_item = Mock()
        mock_item.get = Mock(side_effect=lambda key, default=None: {
            "item_code": "PROD001",
            "description": "Test Product",
            "qty": 2.0,
            "rate": 100.0,
            "amount": 200.0,
            "cfop": 5102,
            "ncm": "12345678"
        }.get(key, default))
        
        mock_invoice = Mock()
        mock_invoice.get = Mock(side_effect=lambda key, default=None: {
            "operation_nature": "VENDA",
            "customer": "CUST-001",
            "customer_name": "Test Customer",
            "total_amount": 200.0,
            "items": [mock_item]
        }.get(key, default))
        mock_invoice.items = [mock_item]
        
        # Build payload
        payload = product_invoice.build_invoice_payload(mock_invoice)
        
        # Assertions
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertEqual(item["code"], "PROD001")
        self.assertEqual(item["quantity"], 2.0)
        self.assertEqual(item["unitAmount"], 100.0)
        self.assertEqual(item["totalAmount"], 200.0)
        self.assertIn("tax", item)
    
    def test_missing_api_token(self):
        """Test operations with missing API token"""
        # Remove API token
        self.nfeio_config.api_token = None
        
        # Test various operations
        with self.assertRaises(product_invoice.NFeIOAPIError) as context:
            product_invoice.issue_product_invoice(
                self.sample_invoice_data, 
                self.nfeio_config
            )
        self.assertIn("API token not configured", str(context.exception))
    
    def test_missing_invoice_id(self):
        """Test operations requiring invoice ID without providing it"""
        # Test cancel without invoice ID
        with self.assertRaises(product_invoice.NFeIOAPIError) as context:
            product_invoice.cancel_product_invoice(
                "", 
                "Test reason", 
                self.nfeio_config
            )
        self.assertIn("Invoice ID is required", str(context.exception))
        
        # Test get events without invoice ID
        with self.assertRaises(product_invoice.NFeIOAPIError) as context:
            product_invoice.get_invoice_events(
                None, 
                self.nfeio_config
            )
        self.assertIn("Invoice ID is required", str(context.exception))


class TestProductInvoiceIntegration(FrappeTestCase):
    """Integration tests with Frappe framework"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests"""
        super().setUpClass()
        # Note: These tests assume Product Invoice doctype exists
        # Adjust based on your actual doctype structure
    
    def test_nfeio_config_exists(self):
        """Test that NFeIO doctype is accessible"""
        # This is a basic smoke test
        self.assertTrue(frappe.get_meta("NFeIO"))
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_whitelist_issue_product_invoice(self, mock_requests):
        """Test whitelisted issue_product_invoice endpoint"""
        from frappe_brazil_invoice.brazil_invoice.doctype.nfeio import nfeio
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"id": "nfe_test123"}
        mock_response.content = b'{"id":"nfe_test123"}'
        mock_requests.post.return_value = mock_response
        
        # Mock NFe.io config retrieval
        with patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio._get_valid_nfeio_config') as mock_config:
            mock_nfeio = Mock()
            mock_nfeio.api_token = "test_token"
            mock_nfeio.company_id = "test_company"
            mock_config.return_value = mock_nfeio
            
            # Test with dict
            result = nfeio.issue_product_invoice({"operationType": "Outgoing"})
            self.assertTrue(result["success"])
            
            # Test with JSON string
            result = nfeio.issue_product_invoice('{"operationType": "Outgoing"}')
            self.assertTrue(result["success"])
    
    def test_whitelist_issue_product_invoice_no_config(self):
        """Test issue_product_invoice endpoint without configuration"""
        from frappe_brazil_invoice.brazil_invoice.doctype.nfeio import nfeio
        
        # Mock no config found
        with patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio._get_valid_nfeio_config') as mock_config:
            mock_config.return_value = None
            
            result = nfeio.issue_product_invoice({})
            self.assertFalse(result["success"])
            self.assertIn("No valid NFe.io configuration", result["error"])


def run_tests():
    """Helper function to run all tests"""
    unittest.main()


if __name__ == "__main__":
    run_tests()
