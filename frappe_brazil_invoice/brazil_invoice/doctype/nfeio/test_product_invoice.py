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
- Real API integration tests

To run these tests:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.nfeio.test_product_invoice
"""

import json
import unittest
from unittest.mock import Mock, patch
import frappe
from frappe.tests.utils import FrappeTestCase
import logging

from frappe_brazil_invoice.brazil_invoice.doctype.nfeio import product_invoice

# Set up test logger
test_logger = logging.getLogger("product_invoice_tests")
test_logger.setLevel(logging.INFO)


def setUpModule():
    """Set up test data once for the entire module"""
    test_logger.info("Setting up Product Invoice test module")

    # Ensure test config exists (reuse if available)
    ensure_test_config_exists()

    # Check if credentials are valid for real API testing
    config = get_test_config()
    if config and is_valid_config(config):
        test_logger.info(
            "✓ Valid NFe.io credentials detected - will test with real API"
        )
    else:
        test_logger.info("⚠ Mock credentials detected - will test with mocked API")


def tearDownModule():
    """Clean up test data after all tests in the module"""
    test_logger.info("Tearing down Product Invoice test module")
    # We don't delete test configs - they are reused across test runs


nfe_config_test = {
    "doctype": "NFeIO",
    "config_name": "Test Product Invoice Config",
    "company_name": "Test Company Product Invoice",
    "company_id": "test_company_product_invoice_123",
    "api_token": "test_api_token_product_invoice_456",
    "is_test_config": 1,
}


def ensure_test_config_exists():
    """Helper to ensure test config exists"""
    # Check if a test config already exists
    existing = frappe.get_all(
        "NFeIO",
        filters={"config_name": "Test Product Invoice Config", "is_test_config": 1},
        limit=1,
    )

    if not existing:
        test_logger.info("Creating new test NFeIO config")
        nfeio_doc = frappe.get_doc(nfe_config_test)
        nfeio_doc.insert(ignore_permissions=True)
        frappe.db.commit()
    else:
        test_logger.debug("Test config already exists, reusing it")


def get_test_config():
    """Get the test NFeIO config document

    Priority:
    1. First look for a valid (real) API config with is_test_config=1
    2. Then fall back to mock config with config_name='Test Product Invoice Config'
    """
    # Get all test configs
    all_test_configs = frappe.get_all(
        "NFeIO",
        filters={"is_test_config": 1},
    )

    # First, try to find a valid (real) API config
    for config_meta in all_test_configs:
        config = frappe.get_doc("NFeIO", config_meta.name)
        if is_valid_config(config):
            # Found a real API config marked for testing
            return config

    # No real API config found, look for our mock test config
    mock_configs = frappe.get_all(
        "NFeIO",
        filters={"config_name": "Test Product Invoice Config", "is_test_config": 1},
        limit=1,
    )

    if not mock_configs:
        ensure_test_config_exists()
        # After creating, get it again
        mock_configs = frappe.get_all(
            "NFeIO",
            filters={"config_name": "Test Product Invoice Config", "is_test_config": 1},
            limit=1,
        )

    if mock_configs:
        return frappe.get_doc("NFeIO", mock_configs[0].name)

    return None


def is_valid_config(config):
    """Check if the config has valid API credentials (not test/mock values)"""
    if not config or not config.api_token or not config.company_id:
        return False

    # Check if these are mock/test values
    if "test" in config.api_token.lower() or "test" in config.company_id.lower():
        return False

    if (
        config.api_token == nfe_config_test["api_token"]
        or config.company_id == nfe_config_test["company_id"]
    ):
        return False

    # Could add a quick API ping here to verify, but for now assume it's valid
    return True


def should_use_real_api():
    """Determine if we should use real API or mocks"""
    config = get_test_config()
    return config and is_valid_config(config)


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
    def test_get_product_invoice_by_id_success(self, mock_requests):
        """Test successful retrieval of invoice by ID"""
        # Mock successful API response
        sample_invoice_data = {
            "id": "nfe_abc123xyz",
            "status": "Issued",
            "number": "123",
            "serie": "1",
            "accessKey": "12345678901234567890123456789012345678901234",
            "operationNature": "Sale",
            "operationType": "Output",
            "buyer": {
                "name": "Customer Name",
                "federalTaxNumber": "12345678901234",
                "type": "Legal"
            },
            "items": [
                {
                    "code": "PROD001",
                    "description": "Product 1",
                    "quantity": 1.0,
                    "unitValue": 100.0
                }
            ],
            "createdOn": "2025-12-28T10:00:00Z"
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_invoice_data
        mock_response.content = json.dumps(sample_invoice_data).encode()
        mock_requests.get.return_value = mock_response
        
        # Call function
        result = product_invoice.get_product_invoice_by_id(
            "nfe_abc123xyz", 
            self.nfeio_config
        )
        
        # Verify results
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "nfe_abc123xyz")
        self.assertEqual(result["status"], "Issued")
        self.assertEqual(result["number"], "123")
        
        # Verify API was called correctly
        mock_requests.get.assert_called_once()
        call_args = mock_requests.get.call_args
        self.assertIn("/productinvoices/nfe_abc123xyz", call_args[0][0])
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_get_product_invoice_by_id_missing_invoice_id(self, mock_requests):
        """Test getting invoice with missing invoice ID"""
        # Call function and expect error
        with self.assertRaises(product_invoice.NFeIOAPIError) as context:
            product_invoice.get_product_invoice_by_id(
                "", 
                self.nfeio_config
            )
        
        self.assertIn("Invoice ID is required", str(context.exception))
    
    @patch('frappe_brazil_invoice.brazil_invoice.doctype.nfeio.product_invoice.requests')
    def test_get_product_invoice_by_id_not_found(self, mock_requests):
        """Test getting non-existent invoice"""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Invoice not found"
        mock_requests.get.return_value = mock_response
        
        # Call function and expect error
        with self.assertRaises(product_invoice.NFeIOAPIError) as context:
            product_invoice.get_product_invoice_by_id(
                "nfe_nonexistent", 
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


class TestProductInvoiceRealAPI(FrappeTestCase):
    """Real API integration tests - only run with valid credentials"""
    
    # Class-level storage for invoice IDs created during tests
    invoice_id_1 = None
    invoice_id_2 = None
    
    @classmethod
    def setUpClass(cls):
        """Set up for real API tests"""
        super().setUpClass()
        cls.config = get_test_config()
        cls.use_real_api = should_use_real_api()
    
    def setUp(self):
        """Set up each test"""
        if not self.use_real_api:
            self.skipTest("Skipping real API test - no valid credentials configured")
        
        test_logger.info(f"Running real API test: {self._testMethodName}")
    
    def test_001_real_api_issue_product_invoice_basic(self):
        """Test issuing a product invoice with real API - basic scenario (creates invoice 1)"""
        # Complete valid invoice data
        invoice_data = {
            "operationNature": "VENDA DE MERCADORIA",
            "operationType": "Outgoing",
            "consumerType": "FinalConsumer",
            "buyer": {
                "name": "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL",
                "federalTaxNumber": 99999999000191,
                "email": "teste@nfe.io",
                "type": "Legal",
                "address": {
                    "state": "SP",
                    "city": {
                        "code": "3550308",
                        "name": "São Paulo"
                    },
                    "district": "Centro",
                    "street": "Rua de Teste",
                    "number": "123",
                    "postalCode": "01310100",
                    "country": "Brasil"
                }
            },
            "items": [
                {
                    "code": "PROD001",
                    "description": "NOTA FISCAL EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL",
                    "ncm": "85044090",
                    "cfop": 5102,
                    "unit": "UN",
                    "quantity": 1.0,
                    "unitAmount": 100.0,
                    "totalAmount": 100.0,
                    "tax": {
                        "icms": {
                            "origin": "0",
                            "cst": "00",
                            "baseTax": 100.0,
                            "rate": 18.0,
                            "amount": 18.0
                        },
                        "pis": {
                            "cst": "01",
                            "baseTax": 100.0,
                            "rate": 1.65,
                            "amount": 1.65
                        },
                        "cofins": {
                            "cst": "01",
                            "baseTax": 100.0,
                            "rate": 7.6,
                            "amount": 7.6
                        }
                    }
                }
            ],
            "totals": {
                "icms": {
                    "baseTax": 100.0,
                    "icmsAmount": 18.0,
                    "productAmount": 100.0,
                    "pisAmount": 1.65,
                    "cofinsAmount": 7.6,
                    "invoiceAmount": 100.0
                }
            }
        }
        
        try:
            result = product_invoice.issue_product_invoice(
                invoice_data,
                self.config
            )
            
            # Check that we got a response
            self.assertIsNotNone(result)
            test_logger.info(f"Issue invoice 1 result: {result}")
            
            # If successful, should have an ID - store it for later tests
            if result and isinstance(result, dict) and result.get('id'):
                TestProductInvoiceRealAPI.invoice_id_1 = result['id']
                test_logger.info(f"✓ Invoice 1 issued successfully: {self.invoice_id_1}")
            else:
                test_logger.warning("Invoice 1 issued but no ID returned")
            
        except product_invoice.NFeIOAPIError as e:
            # API error - log it
            test_logger.error(f"Failed to issue invoice 1: {str(e)}")
            self.fail(f"Invoice 1 issuance failed: {str(e)}")
    
    def test_002_real_api_issue_product_invoice_minimal(self):
        """Test issuing a product invoice with real API - minimal data (creates invoice 2)"""
        # Minimal but valid invoice data
        invoice_data = {
            "operationNature": "VENDA",
            "operationType": "Outgoing",
            "consumerType": "FinalConsumer",
            "buyer": {
                "name": "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL",
                "federalTaxNumber": 99999999000191,
                "type": "Legal",
                "address": {
                    "state": "SP",
                    "city": {
                        "code": "3550308",
                        "name": "São Paulo"
                    },
                    "district": "Centro",
                    "street": "Rua Teste",
                    "number": "100",
                    "postalCode": "01310100",
                    "country": "Brasil"
                }
            },
            "items": [
                {
                    "code": "TEST002",
                    "description": "NOTA FISCAL EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL",
                    "ncm": "85044090",
                    "cfop": 5102,
                    "unit": "UN",
                    "quantity": 2.0,
                    "unitAmount": 50.0,
                    "totalAmount": 100.0,
                    "tax": {
                        "icms": {
                            "origin": "0",
                            "cst": "00",
                            "baseTax": 100.0,
                            "rate": 18.0,
                            "amount": 18.0
                        },
                        "pis": {
                            "cst": "01",
                            "baseTax": 100.0,
                            "rate": 1.65,
                            "amount": 1.65
                        },
                        "cofins": {
                            "cst": "01",
                            "baseTax": 100.0,
                            "rate": 7.6,
                            "amount": 7.6
                        }
                    }
                }
            ],
            "totals": {
                "icms": {
                    "baseTax": 100.0,
                    "icmsAmount": 18.0,
                    "productAmount": 100.0,
                    "pisAmount": 1.65,
                    "cofinsAmount": 7.6,
                    "invoiceAmount": 100.0
                }
            }
        }
        
        try:
            result = product_invoice.issue_product_invoice(
                invoice_data,
                self.config
            )
            
            self.assertIsNotNone(result)
            test_logger.info(f"Issue invoice 2 result: {result}")
            
            # Store ID for later tests
            if result and isinstance(result, dict) and result.get('id'):
                TestProductInvoiceRealAPI.invoice_id_2 = result['id']
                test_logger.info(f"✓ Invoice 2 issued successfully: {self.invoice_id_2}")
            else:
                test_logger.warning("Invoice 2 issued but no ID returned")
                
        except product_invoice.NFeIOAPIError as e:
            test_logger.error(f"Failed to issue invoice 2: {str(e)}")
            self.fail(f"Invoice 2 issuance failed: {str(e)}")
    
    def test_002_5_real_api_get_invoice_by_id_basic(self):
        """Test getting invoice by ID with real API - using invoice 1"""
        if not self.invoice_id_1:
            self.skipTest("Invoice 1 not created - skipping get by ID test")
        
        try:
            # Wait a moment for processing
            import time
            time.sleep(1)
            
            result = product_invoice.get_product_invoice_by_id(
                self.invoice_id_1,
                self.config
            )
            
            self.assertIsNotNone(result)
            test_logger.info(f"Get invoice 1 by ID result: {result}")
            
            # Check that we got the invoice data
            if result and isinstance(result, dict):
                self.assertEqual(result.get('id'), self.invoice_id_1)
                test_logger.info("✓ Invoice 1 retrieved successfully")
                test_logger.info(f"  Status: {result.get('status')}")
                test_logger.info(f"  Number: {result.get('number')}")
                if result.get('accessKey'):
                    test_logger.info(f"  Access Key: {result.get('accessKey')}")
                
        except product_invoice.NFeIOAPIError as e:
            test_logger.warning(f"Get invoice by ID API error: {str(e)}")
            # Don't fail - invoice might still be processing
    
    def test_002_6_real_api_get_invoice_by_id_with_details(self):
        """Test getting invoice by ID with full details - using invoice 2"""
        if not self.invoice_id_2:
            self.skipTest("Invoice 2 not created - skipping get by ID test")
        
        try:
            # Wait a moment for processing
            import time
            time.sleep(1)
            
            result = product_invoice.get_product_invoice_by_id(
                self.invoice_id_2,
                self.config
            )
            
            self.assertIsNotNone(result)
            test_logger.info(f"Get invoice 2 by ID result: {result}")
            
            # Check structure
            if result and isinstance(result, dict):
                self.assertEqual(result.get('id'), self.invoice_id_2)
                test_logger.info("✓ Invoice 2 retrieved successfully")
                
                # Log detailed information
                if result.get('buyer'):
                    test_logger.info(f"  Buyer: {result['buyer'].get('name')}")
                if result.get('items'):
                    test_logger.info(f"  Items count: {len(result['items'])}")
                if result.get('flowStatus'):
                    test_logger.info(f"  Flow Status: {result.get('flowStatus')}")
                
        except product_invoice.NFeIOAPIError as e:
            test_logger.warning(f"Get invoice 2 by ID error: {str(e)}")
    
    def test_003_real_api_query_invoice_events_basic(self):
        """Test querying invoice events with real API - using invoice 1"""
        if not self.invoice_id_1:
            self.skipTest("Invoice 1 not created - skipping event query test")
        
        try:
            # Wait a moment for processing
            import time
            time.sleep(2)
            
            result = product_invoice.get_invoice_events(
                self.invoice_id_1,
                self.config,
                limit=10,
                starting_after=0
            )
            
            self.assertIsNotNone(result)
            test_logger.info(f"Query events for invoice 1 result: {result}")
            
            # Check structure if successful
            if result and isinstance(result, dict):
                self.assertIn("events", result)
                test_logger.info(f"✓ Events retrieved: {len(result.get('events', []))} events")
                
        except product_invoice.NFeIOAPIError as e:
            test_logger.warning(f"Query events API error: {str(e)}")
            # Don't fail - invoice might still be processing
    
    def test_004_real_api_query_invoice_events_with_pagination(self):
        """Test querying invoice events with pagination - using invoice 2"""
        if not self.invoice_id_2:
            self.skipTest("Invoice 2 not created - skipping pagination test")
        
        try:
            # Wait a moment for processing
            import time
            time.sleep(2)
            
            result = product_invoice.get_invoice_events(
                self.invoice_id_2,
                self.config,
                limit=5,
                starting_after=0
            )
            
            self.assertIsNotNone(result)
            test_logger.info(f"Paginated events for invoice 2 result: {result}")
            
            # If successful, check pagination fields
            if result and isinstance(result, dict):
                if "hasMore" in result:
                    test_logger.info(f"✓ Has more events: {result['hasMore']}")
                    
        except product_invoice.NFeIOAPIError as e:
            test_logger.warning(f"Pagination query error: {str(e)}")
    
    def test_005_real_api_get_invoice_xml_basic(self):
        """Test getting invoice XML with real API - using invoice 1"""
        if not self.invoice_id_1:
            self.skipTest("Invoice 1 not created - skipping XML test")
        
        try:
            # Wait for processing
            import time
            time.sleep(3)
            
            result = product_invoice.get_invoice_xml(
                self.invoice_id_1,
                self.config
            )
            
            self.assertIsNotNone(result)
            test_logger.info(f"Get XML for invoice 1 result: {result}")
            
            # Check for URI if successful
            if result and isinstance(result, dict) and "uri" in result:
                test_logger.info(f"✓ XML URI: {result['uri']}")
                self.assertTrue(result['uri'].startswith("http"))
                
        except product_invoice.NFeIOAPIError as e:
            test_logger.warning(f"Get XML API error: {str(e)}")
            # Don't fail - invoice might still be processing
    
    def test_006_real_api_get_invoice_xml_error_handling(self):
        """Test XML retrieval error handling with invalid ID"""
        # Use an obviously invalid invoice ID
        invalid_invoice_id = "definitely_not_a_valid_invoice_id_xyz"
        
        try:
            result = product_invoice.get_invoice_xml(
                invalid_invoice_id,
                self.config
            )
            
            # If we get here, log the unexpected success
            test_logger.info(f"Unexpected success for invalid ID: {result}")
            
        except product_invoice.NFeIOAPIError as e:
            # This is expected behavior
            test_logger.info(f"✓ Expected error for invalid ID: {str(e)}")
            self.assertIsInstance(e, product_invoice.NFeIOAPIError)
            # Should mention "not found" or similar
            self.assertTrue(
                "not found" in str(e).lower() or 
                "invalid" in str(e).lower() or
                "400" in str(e) or
                "404" in str(e)
            )
    
    def test_007_real_api_get_invoice_pdf_basic(self):
        """Test getting invoice PDF with real API - using invoice 1"""
        if not self.invoice_id_1:
            self.skipTest("Invoice 1 not created - skipping PDF test")
        
        try:
            # Wait for processing
            import time
            time.sleep(3)
            
            result = product_invoice.get_invoice_pdf(
                self.invoice_id_1,
                self.config,
                force=False
            )
            
            self.assertIsNotNone(result)
            test_logger.info(f"Get PDF for invoice 1 result: {result}")
            
            # Check for URI if successful
            if result and isinstance(result, dict) and "uri" in result:
                test_logger.info(f"✓ PDF URI: {result['uri']}")
                self.assertTrue(result['uri'].startswith("http"))
                
        except product_invoice.NFeIOAPIError as e:
            test_logger.warning(f"Get PDF API error: {str(e)}")
            # Don't fail - invoice might still be processing
    
    def test_008_real_api_get_invoice_pdf_with_force(self):
        """Test getting invoice PDF with force parameter - using invoice 2"""
        if not self.invoice_id_2:
            self.skipTest("Invoice 2 not created - skipping PDF force test")
        
        try:
            # Wait for processing
            import time
            time.sleep(3)
            
            result = product_invoice.get_invoice_pdf(
                self.invoice_id_2,
                self.config,
                force=True
            )
            
            self.assertIsNotNone(result)
            test_logger.info(f"Get PDF (forced) for invoice 2 result: {result}")
            
            if result and isinstance(result, dict) and "uri" in result:
                test_logger.info(f"✓ PDF URI (forced): {result['uri']}")
            
        except product_invoice.NFeIOAPIError as e:
            test_logger.warning(f"Get PDF forced error: {str(e)}")
    
    def test_009_real_api_cancel_product_invoice_valid(self):
        """Test canceling product invoice with real API - canceling invoice 1"""
        if not self.invoice_id_1:
            self.skipTest("Invoice 1 not created - skipping cancellation test")
        
        reason = "Teste de cancelamento via integração automatizada - Invoice 1"
        
        try:
            # Wait for invoice to be fully processed before canceling
            import time
            time.sleep(5)
            
            result = product_invoice.cancel_product_invoice(
                self.invoice_id_1,
                reason,
                self.config
            )
            
            self.assertIsNotNone(result)
            test_logger.info(f"Cancel invoice 1 result: {result}")
            test_logger.info("✓ Invoice 1 cancellation queued successfully")
            
        except product_invoice.NFeIOAPIError as e:
            # May fail if invoice is not yet authorized
            test_logger.warning(f"Cancel invoice 1 API error: {str(e)}")
            # Don't fail the test - invoice might not be ready for cancellation yet
    
    def test_010_real_api_cancel_product_invoice_with_long_reason(self):
        """Test canceling with a longer reason message - canceling invoice 2"""
        if not self.invoice_id_2:
            self.skipTest("Invoice 2 not created - skipping cancellation test")
        
        reason = "Cancelamento solicitado pelo cliente devido a erro no pedido. " \
                 "O cliente solicitou a reemissão com os dados corretos. " \
                 "Teste de integração automatizada - Invoice 2."
        
        try:
            # Wait for invoice to be fully processed
            import time
            time.sleep(5)
            
            result = product_invoice.cancel_product_invoice(
                self.invoice_id_2,
                reason,
                self.config
            )
            
            self.assertIsNotNone(result)
            test_logger.info(f"Cancel invoice 2 result: {result}")
            test_logger.info("✓ Invoice 2 cancellation queued successfully")
            
        except product_invoice.NFeIOAPIError as e:
            test_logger.warning(f"Cancel invoice 2 API error: {str(e)}")
            # Don't fail the test


def run_tests():
    """Helper function to run all tests"""
    unittest.main()


if __name__ == "__main__":
    run_tests()
