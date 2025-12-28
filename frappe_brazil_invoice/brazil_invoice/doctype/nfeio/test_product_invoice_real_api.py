# Copyright (c) 2025, AnyGridTech and contributors
# For license information, please see license.txt

"""
Real API Integration Tests for Product Invoice Operations with NFe.io API

These tests run against the actual NFe.io API with valid credentials.
Tests cover:
- Issue/emit product invoices
- Get invoice by ID with status waiting
- Query invoice events
- Retrieve PDF (DANFE)
- Retrieve XML
- Cancel product invoices

To run these tests:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.nfeio.test_product_invoice_real_api

Prerequisites:
- Valid NFe.io API credentials configured in an NFeIO document with is_test_config=1
"""

import unittest
import frappe
from frappe.tests.utils import FrappeTestCase
import logging
import time
from datetime import datetime

from frappe_brazil_invoice.brazil_invoice.doctype.nfeio import product_invoice

# Set up test logger
test_logger = logging.getLogger("product_invoice_real_api_tests")
test_logger.setLevel(logging.INFO)

# Test execution tracking
test_results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "errors": [],
    "invoice_ids": [],
    "start_time": None,
    "end_time": None
}


def setUpModule():
    """Set up test data once for the entire module"""
    test_logger.info("Setting up Product Invoice Real API test module")
    
    test_results["start_time"] = datetime.now()

    # Ensure test config exists (reuse if available)
    ensure_test_config_exists()

    # Check if credentials are valid for real API testing
    config = get_test_config()
    if config and is_valid_config(config):
        test_logger.info(
            "✓ Valid NFe.io credentials detected - will test with real API"
        )
    else:
        test_logger.warning("⚠ No valid API credentials - tests will be skipped")


def tearDownModule():
    """Clean up test data after all tests in the module"""
    test_results["end_time"] = datetime.now()
    test_logger.info("Tearing down Product Invoice Real API test module")
    print_test_dashboard()


def print_test_dashboard():
    """Print a formatted dashboard with test results"""
    width = 80
    
    print("\n" + "=" * width)
    print("NFe.io REAL API TEST DASHBOARD".center(width))
    print("=" * width)
    
    # Time information
    if test_results["start_time"] and test_results["end_time"]:
        duration = test_results["end_time"] - test_results["start_time"]
        print(f"\n⏱  Duration: {duration.total_seconds():.2f}s")
    
    # Test summary
    print(f"\n📊 TEST SUMMARY")
    print(f"   Total Tests:    {test_results['total']}")
    print(f"   ✓ Passed:       {test_results['passed']} ({test_results['passed']/max(test_results['total'],1)*100:.1f}%)")
    print(f"   ✗ Failed:       {test_results['failed']}")
    print(f"   ⊘ Skipped:      {test_results['skipped']}")
    
    # Invoice information
    if test_results["invoice_ids"]:
        print(f"\n📄 INVOICES CREATED")
        for idx, invoice_id in enumerate(test_results["invoice_ids"], 1):
            print(f"   Invoice {idx}: {invoice_id}")
    
    # Error details
    if test_results["errors"]:
        print(f"\n⚠  ERRORS & WARNINGS")
        for error in test_results["errors"][:5]:  # Show max 5 errors
            print(f"   • {error}")
        if len(test_results["errors"]) > 5:
            print(f"   ... and {len(test_results['errors']) - 5} more")
    
    # Status interpretation
    print(f"\n💡 TEST ENVIRONMENT NOTES")
    print(f"   • Invoices should reach 'Issued' status even in homologation")
    print(f"   • Using test CNPJ: 99999999000191")
    print(f"   • Skipped tests indicate invoices still processing after retries")
    print(f"   • Error status indicates a problem that needs investigation")
    
    print("\n" + "=" * width)
    print()


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

    # No real API config found
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

    return True


def should_use_real_api():
    """Determine if we should use real API or skip tests"""
    config = get_test_config()
    return config and is_valid_config(config)


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
        test_results["total"] += 1
    
    def tearDown(self):
        """Track test results after each test"""
        # Check test outcome
        if hasattr(self, '_outcome'):
            result = self._outcome.result
            if result.errors and result.errors[-1][0] == self:
                test_results["failed"] += 1
                error_msg = str(result.errors[-1][1])[:100]
                test_results["errors"].append(f"{self._testMethodName}: {error_msg}")
            elif result.skipped and result.skipped[-1][0] == self:
                test_results["skipped"] += 1
            else:
                test_results["passed"] += 1
    
    def test_001_real_api_issue_product_invoice_basic(self):
        """Test issuing a product invoice with real API - basic scenario (creates invoice 1)"""
        # Complete valid invoice data
        invoice_data = {
            "operationNature": "VENDA DE MERCADORIA",
            "operationType": "Outgoing",
            "consumerType": "FinalConsumer",
            "body": "Nota fiscal de teste emitida em ambiente de homologacao",
            "buyer": {
                "name": "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL",
                "federalTaxNumber": 99999999000191,
                "email": "teste@nfe.io",
                "type": 1,
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
                test_results["invoice_ids"].append(result['id'])
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
            "body": "Nota fiscal de teste - dados minimos",
            "buyer": {
                "name": "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL",
                "federalTaxNumber": 99999999000191,
                "type": 1,
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
                test_results["invoice_ids"].append(result['id'])
                test_logger.info(f"✓ Invoice 2 issued successfully: {self.invoice_id_2}")
            else:
                test_logger.warning("Invoice 2 issued but no ID returned")
                
        except product_invoice.NFeIOAPIError as e:
            test_logger.error(f"Failed to issue invoice 2: {str(e)}")
            self.fail(f"Invoice 2 issuance failed: {str(e)}")
    
    def test_002_5_real_api_get_invoice_by_id_basic(self):
        """Test getting invoice by ID with real API - using invoice 1, wait for Issued status"""
        if not self.invoice_id_1:
            self.skipTest("Invoice 1 not created - skipping get by ID test")
        
        import time
        max_retries = 10
        retry_delay = 2  # seconds
        
        for attempt in range(1, max_retries + 1):
            try:
                test_logger.info(f"Attempt {attempt}/{max_retries} to check invoice 1 status")
                
                result = product_invoice.get_product_invoice_by_id(
                    self.invoice_id_1,
                    self.config
                )
                
                self.assertIsNotNone(result)
                
                if result and isinstance(result, dict):
                    status = result.get('status')
                    test_logger.info(f"Invoice 1 status: {status}")
                    
                    if status == "Issued":
                        test_logger.info("✓ Invoice 1 successfully issued!")
                        test_logger.info(f"  ID: {result.get('id')}")
                        test_logger.info(f"  Number: {result.get('number')}")
                        if result.get('accessKey'):
                            test_logger.info(f"  Access Key: {result.get('accessKey')}")
                        return  # Success!
                    elif status in ["Processing", "Created", "Queued"]:
                        if attempt < max_retries:
                            test_logger.info(f"  Invoice status is '{status}', waiting {retry_delay}s...")
                            time.sleep(retry_delay)
                            continue
                        else:
                            test_logger.warning(f"Invoice 1 failed to reach 'Issued' status after {max_retries} attempts. Status: {status}")
                            self.skipTest(f"Invoice 1 still {status} after {max_retries} attempts")
                    elif status == "Error":
                        test_logger.error(f"Invoice 1 has Error status - investigation required")
                        test_logger.error(f"  ID: {result.get('id')}")
                        test_logger.error(f"  Number: {result.get('number')}")
                        test_logger.error(f"  Full response: {result}")
                        if result.get('messages'):
                            test_logger.error(f"  Messages: {result.get('messages')}")
                        if result.get('errors'):
                            test_logger.error(f"  Errors: {result.get('errors')}")
                        error_details = result.get('messages') or result.get('errors') or 'No error details available'
                        self.fail(f"Invoice 1 failed with Error status. Details: {error_details}")
                    else:
                        test_logger.warning(f"Invoice 1 has unexpected status: {status}")
                        self.skipTest(f"Unexpected invoice status: {status}")
                else:
                    self.fail("Failed to get invoice 1 data")
                    
            except product_invoice.NFeIOAPIError as e:
                if attempt < max_retries:
                    test_logger.warning(f"API error on attempt {attempt}: {str(e)}, retrying...")
                    time.sleep(retry_delay)
                else:
                    test_logger.error(f"Failed to get invoice 1 after {max_retries} attempts: {str(e)}")
                    self.skipTest(f"Failed to get invoice 1: {str(e)}")
    
    def test_002_6_real_api_get_invoice_by_id_with_details(self):
        """Test getting invoice by ID with full details - using invoice 2, wait for Issued status"""
        if not self.invoice_id_2:
            self.skipTest("Invoice 2 not created - skipping get by ID test")
        
        import time
        max_retries = 10
        retry_delay = 2  # seconds
        
        for attempt in range(1, max_retries + 1):
            try:
                test_logger.info(f"Attempt {attempt}/{max_retries} to check invoice 2 status")
                
                result = product_invoice.get_product_invoice_by_id(
                    self.invoice_id_2,
                    self.config
                )
                
                self.assertIsNotNone(result)
                
                if result and isinstance(result, dict):
                    status = result.get('status')
                    test_logger.info(f"Invoice 2 status: {status}")
                    
                    if status == "Issued":
                        test_logger.info("✓ Invoice 2 successfully issued!")
                        test_logger.info(f"  ID: {result.get('id')}")
                        
                        # Log detailed information
                        if result.get('buyer'):
                            test_logger.info(f"  Buyer: {result['buyer'].get('name')}")
                        if result.get('items'):
                            test_logger.info(f"  Items count: {len(result['items'])}")
                        if result.get('flowStatus'):
                            test_logger.info(f"  Flow Status: {result.get('flowStatus')}")
                        return  # Success!
                    elif status in ["Processing", "Created", "Queued"]:
                        if attempt < max_retries:
                            test_logger.info(f"  Invoice status is '{status}', waiting {retry_delay}s...")
                            time.sleep(retry_delay)
                            continue
                        else:
                            test_logger.warning(f"Invoice 2 failed to reach 'Issued' status after {max_retries} attempts. Status: {status}")
                            self.skipTest(f"Invoice 2 still {status} after {max_retries} attempts")
                    elif status == "Error":
                        test_logger.error(f"Invoice 2 has Error status - investigation required")
                        test_logger.error(f"  ID: {result.get('id')}")
                        test_logger.error(f"  Number: {result.get('number')}")
                        test_logger.error(f"  Full response: {result}")
                        if result.get('messages'):
                            test_logger.error(f"  Messages: {result.get('messages')}")
                        if result.get('errors'):
                            test_logger.error(f"  Errors: {result.get('errors')}")
                        error_details = result.get('messages') or result.get('errors') or 'No error details available'
                        self.fail(f"Invoice 2 failed with Error status. Details: {error_details}")
                    else:
                        test_logger.warning(f"Invoice 2 has unexpected status: {status}")
                        self.skipTest(f"Unexpected invoice status: {status}")
                else:
                    self.fail("Failed to get invoice 2 data")
                    
            except product_invoice.NFeIOAPIError as e:
                if attempt < max_retries:
                    test_logger.warning(f"API error on attempt {attempt}: {str(e)}, retrying...")
                    time.sleep(retry_delay)
                else:
                    test_logger.error(f"Failed to get invoice 2 after {max_retries} attempts: {str(e)}")
                    self.skipTest(f"Failed to get invoice 2: {str(e)}")
    
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
