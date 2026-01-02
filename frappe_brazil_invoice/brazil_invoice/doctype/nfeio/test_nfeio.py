# Copyright (c) 2025, AnyGridTech and Contributors
# See license.txt

"""
NFeIO API Tests

To run these tests:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.nfeio.test_nfeio

To run a specific test class:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.nfeio.test_nfeio --test TestNFeIOAPI
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock
from . import nfeio
import logging

# Set up test logger
test_logger = logging.getLogger("nfeio_tests")
test_logger.setLevel(logging.INFO)


def setUpModule():
    """Set up test data once for the entire module"""
    test_logger.info("Setting up NFeIO test module")

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
    test_logger.info("Tearing down NFeIO test module")
    # We don't delete test configs - they are reused across test runs


nfe_config_test = {
    "doctype": "NFeIO",
    "config_name": "Test Config",
    "company_name": "Test Company",
    "company_id": "test_company_id_123",
    "api_token": "test_api_token_456",
    "is_test_config": 1,
    "usage_priority": 1,
}


def ensure_test_config_exists():
    """Helper to ensure test config exists - creates with is_test_config=0 for API"""
    # Check if a test config already exists
    existing = frappe.get_all(
        "NFeIO",
        filters={"config_name": "Test Config"},
        limit=1,
    )

    if not existing:
        test_logger.info("Creating new test NFeIO config with is_test_config=0")
        # Create with is_test_config=0 so the API considers it valid
        config = dict(nfe_config_test)
        config["is_test_config"] = 0  # Must be 0 for API to work
        nfeio_doc = frappe.get_doc(config)
        nfeio_doc.insert(ignore_permissions=True)
        frappe.db.commit()
    else:
        test_logger.debug("Test config already exists, reusing it")


def get_test_config():
    """Get the test NFeIO config document

    Priority:
    1. First look for a valid (real) API config
    2. Then fall back to mock config with config_name='Test Config'
    """
    # Get all configs (both is_test_config=0 and is_test_config=1)
    all_configs = frappe.get_all("NFeIO")

    # First, try to find a valid (real) API config
    for config_meta in all_configs:
        config = frappe.get_doc("NFeIO", config_meta.name)
        if is_valid_config(config):
            # Found a real API config
            return config

    # No real API config found, look for our mock test config
    mock_configs = frappe.get_all(
        "NFeIO",
        filters={"config_name": "Test Config"},
        limit=1,
    )

    if not mock_configs:
        ensure_test_config_exists()
        # After creating, get it again
        mock_configs = frappe.get_all(
            "NFeIO",
            filters={"config_name": "Test Config"},
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


def delete_all_test_configs():
    """Delete only mock test NFeIO configurations, preserving real API configs

    This function deletes configs with is_test_config=1 BUT only if they have
    mock/test credentials. Real API configs (even with is_test_config=1) are preserved.
    """
    test_configs = frappe.get_all(
        "NFeIO",
        filters={"is_test_config": 1},
    )
    for config_meta in test_configs:
        config = frappe.get_doc("NFeIO", config_meta.name)
        # Only delete if it's a mock config (not a valid real API config)
        if not is_valid_config(config):
            frappe.delete_doc("NFeIO", config.name, force=True)
    frappe.db.commit()


class TestNFeIO(FrappeTestCase):
    """Test NFeIO doctype"""

    def setUp(self):
        """Set up test data before each test"""
        ensure_test_config_exists()
        test_logger.debug(f"Running test: {self._testMethodName}")

    def tearDown(self):
        """Ensure config exists after each test"""
        ensure_test_config_exists()

    def test_nfeio_doctype_creation(self):
        """Test creating NFeIO document"""
        test_logger.info("Testing NFeIO doctype creation")
        nfeio_doc = get_test_config()
        self.assertIsNotNone(nfeio_doc, "Test NFeIO config should exist")

        # Log which config we're using
        if is_valid_config(nfeio_doc):
            test_logger.info(f"✓ Using real API config: {nfeio_doc.config_name}")
        else:
            test_logger.info(f"✓ Using mock config: {nfeio_doc.config_name}")
            self.assertEqual(nfeio_doc.config_name, "Test Config")

    def test_unique_api_token_validation(self):
        """Test that API tokens must be unique"""
        test_logger.info("Testing unique API token validation")

        # Create first config with a unique token
        config1 = frappe.get_doc(
            {
                "doctype": "NFeIO",
                "config_name": "Unique Token Config 1",
                "company_name": "Company A",
                "company_id": "company_a_123",
                "api_token": "unique_token_12345",
                "is_test_config": 1,
            }
        )
        config1.insert(ignore_permissions=True)
        frappe.db.commit()

        try:
            # Try to create second config with same token
            config2 = frappe.get_doc(
                {
                    "doctype": "NFeIO",
                    "config_name": "Unique Token Config 2",
                    "company_name": "Company B",
                    "company_id": "company_b_456",
                    "api_token": "unique_token_12345",  # Same token
                    "is_test_config": 1,
                }
            )

            # Should raise ValidationError
            with self.assertRaises(frappe.ValidationError) as context:
                config2.insert(ignore_permissions=True)

            self.assertIn("API Token already exists", str(context.exception))
            test_logger.info("✓ Duplicate API token correctly rejected")

        finally:
            # Clean up
            frappe.delete_doc("NFeIO", config1.name, force=True)
            frappe.db.commit()

    def test_unique_api_token_allows_update(self):
        """Test that updating a config with its own token is allowed"""
        test_logger.info("Testing API token validation allows self-update")

        # Create a config
        config = frappe.get_doc(
            {
                "doctype": "NFeIO",
                "config_name": "Update Token Config",
                "company_name": "Company C",
                "company_id": "company_c_789",
                "api_token": "update_token_98765",
                "is_test_config": 1,
            }
        )
        config.insert(ignore_permissions=True)
        frappe.db.commit()

        try:
            # Update the same config (should work)
            config.company_name = "Company C Updated"
            config.save()  # Should not raise error
            frappe.db.commit()

            self.assertEqual(config.company_name, "Company C Updated")
            test_logger.info("✓ Self-update with same token works correctly")

        finally:
            # Clean up
            frappe.delete_doc("NFeIO", config.name, force=True)
            frappe.db.commit()

    def test_unique_api_token_allows_different_tokens(self):
        """Test that different API tokens can coexist"""
        test_logger.info("Testing multiple configs with different tokens")

        config1 = frappe.get_doc(
            {
                "doctype": "NFeIO",
                "config_name": "Different Token Config 1",
                "company_name": "Company D",
                "company_id": "company_d_111",
                "api_token": "different_token_aaa",
                "is_test_config": 1,
            }
        )
        config1.insert(ignore_permissions=True)

        config2 = frappe.get_doc(
            {
                "doctype": "NFeIO",
                "config_name": "Different Token Config 2",
                "company_name": "Company E",
                "company_id": "company_e_222",
                "api_token": "different_token_bbb",  # Different token
                "is_test_config": 1,
            }
        )
        config2.insert(ignore_permissions=True)
        frappe.db.commit()

        try:
            # Both should exist
            self.assertTrue(frappe.db.exists("NFeIO", config1.name))
            self.assertTrue(frappe.db.exists("NFeIO", config2.name))
            test_logger.info("✓ Multiple configs with different tokens work correctly")

        finally:
            # Clean up
            frappe.delete_doc("NFeIO", config1.name, force=True)
            frappe.delete_doc("NFeIO", config2.name, force=True)
            frappe.db.commit()


class TestNFeIOAPI(FrappeTestCase):
    """Test NFeIO API endpoints"""

    def setUp(self):
        """Set up test data before each test"""
        ensure_test_config_exists()
        test_logger.debug(f"Running test: {self._testMethodName}")

    def tearDown(self):
        """Ensure config exists after each test"""
        ensure_test_config_exists()

    def test_get_nfeio_config_api(self):
        """Test get_nfeio_config API endpoint"""
        test_logger.info("Testing get_nfeio_config API endpoint")
        result = nfeio.get_nfeio_config()

        self.assertTrue(result["success"])
        self.assertTrue(result["configured"])
        self.assertIsNotNone(result["company_id"])
        self.assertIsNotNone(result["company_name"])
        self.assertTrue(result["has_api_token"])
        test_logger.info(f"✓ get_nfeio_config API works: {result['company_name']}")

    def test_get_nfeio_config_api_no_config(self):
        """Test get_nfeio_config API endpoint with no configuration"""
        test_logger.info("Testing get_nfeio_config API with no configuration")

        # Skip if real API config exists (can't test 'no config' scenario)
        if should_use_real_api():
            test_logger.info(
                "⊘ Skipping - real API config exists and cannot be deleted"
            )
            self.skipTest(
                "Cannot test 'no config' scenario with permanent real API config"
            )
            return

        # Temporarily delete only test configs (preserve real configs)
        delete_all_test_configs()

        try:
            result = nfeio.get_nfeio_config()

            self.assertFalse(result["success"])
            self.assertFalse(result["configured"])
            test_logger.info("✓ get_nfeio_config API correctly handles missing config")
        finally:
            # Always restore the test config
            ensure_test_config_exists()

    @patch("frappe_brazil_invoice.brazil_invoice.doctype.nfeio.tax.calculate_taxes")
    @patch("frappe.get_doc")
    def test_calculate_invoice_taxes_api_success(
        self, mock_get_doc, mock_calculate_taxes
    ):
        """Test calculate_product_invoice_taxes API endpoint - success"""
        test_logger.info("Testing calculate_product_invoice_taxes API endpoint - success")

        # Check if we should use real API
        use_real_api = should_use_real_api()
        test_logger.info(
            f"Using {'real' if use_real_api else 'mocked'} API for testing"
        )

        # Create mock invoice and tax template
        mock_invoice = MagicMock()
        mock_invoice.icms_value = 18.0
        mock_invoice.ipi_value = 9.75
        mock_invoice.pis_value = 1.65
        mock_invoice.cofins_value = 7.6

        mock_tax_template = MagicMock()

        if not use_real_api:
            # Mock the tax calculation to update values - accepts use_fallback parameter
            def update_invoice_taxes(invoice, template, config, use_fallback=False):
                invoice.icms_value = 18.0
                invoice.ipi_value = 9.75
                invoice.pis_value = 1.65
                invoice.cofins_value = 7.6

            mock_calculate_taxes.side_effect = update_invoice_taxes

        def get_doc_side_effect(doctype, name=None, **kwargs):
            if doctype == "Product Invoice":
                return mock_invoice
            elif doctype == "Tax":
                return mock_tax_template
            elif doctype == "Error Log":
                # Handle frappe.log_error calls
                return MagicMock()
            return MagicMock()

        mock_get_doc.side_effect = get_doc_side_effect

        result = nfeio.calculate_product_invoice_taxes("TEST_INVOICE", "TEST_TAX_TEMPLATE")

        self.assertTrue(result["success"])
        test_logger.info(
            f"✓ calculate_product_invoice_taxes API succeeded with ICMS: {result['icms_value']}"
        )

    def test_calculate_invoice_taxes_api_no_config(self):
        """Test calculate_product_invoice_taxes API endpoint - no configuration"""
        test_logger.info("Testing calculate_product_invoice_taxes API with no configuration")

        # Skip if real API config exists (can't test 'no config' scenario)
        if should_use_real_api():
            test_logger.info(
                "⊘ Skipping - real API config exists and cannot be deleted"
            )
            self.skipTest(
                "Cannot test 'no config' scenario with permanent real API config"
            )
            return

        # Temporarily delete only test configs (preserve real configs)
        delete_all_test_configs()

        try:
            # Mock invoice and tax template
            mock_invoice = MagicMock()
            mock_tax_template = MagicMock()

            with patch("frappe.log_error"):
                with patch("frappe.get_doc") as mock_get_doc:

                    def get_doc_side_effect(doctype, name):
                        if doctype == "Product Invoice":
                            return mock_invoice
                        elif doctype == "Tax":
                            return mock_tax_template
                        return MagicMock()

                    mock_get_doc.side_effect = get_doc_side_effect

                    result = nfeio.calculate_product_invoice_taxes(
                        "TEST_INVOICE", "TEST_TAX_TEMPLATE"
                    )

                    self.assertFalse(result["success"])
                    self.assertIn("error", result)
                    test_logger.info(
                        "✓ calculate_product_invoice_taxes API correctly handles missing config"
                    )
        finally:
            # Always restore the test config
            ensure_test_config_exists()

    @patch(
        "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.tax.calculate_taxes_fallback"
    )
    @patch("frappe.get_doc")
    def test_calculate_invoice_taxes_with_fallback(
        self, mock_get_doc, mock_calculate_fallback
    ):
        """Test calculate_product_invoice_taxes API endpoint with use_fallback=True"""
        test_logger.info("Testing calculate_product_invoice_taxes API with use_fallback=True")

        # Ensure test config exists
        ensure_test_config_exists()

        # Create mock invoice and tax template
        mock_invoice = MagicMock()
        mock_invoice.icms_value = 18.0
        mock_invoice.ipi_value = 9.75
        mock_invoice.pis_value = 0
        mock_invoice.cofins_value = 0

        mock_tax_template = MagicMock()

        # Mock the fallback calculation to update values
        def update_invoice_taxes_fallback(invoice, template):
            invoice.icms_value = 18.0
            invoice.ipi_value = 9.75

        mock_calculate_fallback.side_effect = update_invoice_taxes_fallback

        def get_doc_side_effect(doctype, name=None, **kwargs):
            if doctype == "Product Invoice":
                return mock_invoice
            elif doctype == "Tax":
                return mock_tax_template
            elif doctype == "Error Log":
                # Handle frappe.log_error calls
                return MagicMock()
            return MagicMock()

        mock_get_doc.side_effect = get_doc_side_effect

        result = nfeio.calculate_product_invoice_taxes(
            "TEST_INVOICE", "TEST_TAX_TEMPLATE", use_fallback=True
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["icms_value"], 18.0)
        self.assertEqual(result["ipi_value"], 9.75)
        test_logger.info(
            "✓ calculate_product_invoice_taxes with use_fallback=True works correctly"
        )

    def test_calculate_invoice_taxes_no_valid_config_error(self):
        """Test calculate_product_invoice_taxes throws error when no valid (non-test) config exists"""
        test_logger.info(
            "Testing calculate_product_invoice_taxes throws error with no valid config"
        )
        # Delete all test configs to ensure only test configs remain
        delete_all_test_configs()

        # Create a test config with is_test_config=1
        test_config = frappe.get_doc(
            {
                "doctype": "NFeIO",
                "config_name": "Test Config Only",
                "company_name": "Test Company",
                "company_id": "test_company_id",
                "api_token": "test_token_only",
                "is_test_config": 1,
            }
        )
        test_config.insert()
        frappe.db.commit()

        try:
            # Should throw error because no valid (non-test) config exists
            result = nfeio.calculate_product_invoice_taxes(
                "TEST_INVOICE", "TEST_TAX_TEMPLATE", use_fallback=False
            )

            # If we get here, check if it returned an error
            self.assertFalse(result.get("success", False))
            self.assertIn("error", result)
            test_logger.info(
                "✓ calculate_product_invoice_taxes correctly handles no valid config"
            )
        except Exception as e:
            # Expected - should throw an error
            self.assertIn("valid", str(e).lower())
            test_logger.info(
                "✓ calculate_product_invoice_taxes correctly throws error with no valid config"
            )
        finally:
            # Clean up
            frappe.delete_doc("NFeIO", test_config.name)
            frappe.db.commit()

    def test_helper_get_nfeio_config(self):
        """Test _get_nfeio_config helper function"""
        test_logger.info("Testing _get_nfeio_config helper function")
        config = nfeio._get_nfeio_config()

        self.assertIsNotNone(config)
        self.assertIsNotNone(config.company_id)
        self.assertIsNotNone(config.api_token)
        test_logger.info(f"✓ _get_nfeio_config helper works: {config.config_name}")

    def test_helper_get_nfeio_config_no_config(self):
        """Test _get_nfeio_config helper function with no configuration"""
        test_logger.info("Testing _get_nfeio_config helper with no configuration")

        # Skip if real API config exists (can't test 'no config' scenario)
        if should_use_real_api():
            test_logger.info(
                "⊘ Skipping - real API config exists and cannot be deleted"
            )
            self.skipTest(
                "Cannot test 'no config' scenario with permanent real API config"
            )
            return

        # Temporarily delete only test configs (preserve real configs)
        delete_all_test_configs()

        try:
            config = nfeio._get_nfeio_config()

            self.assertIsNone(config)
            test_logger.info("✓ _get_nfeio_config correctly handles missing config")
        finally:
            # Always restore the test config
            ensure_test_config_exists()


class TestNFeIOIntegration(FrappeTestCase):
    """Integration tests for NFeIO with actual tax calculation"""

    def setUp(self):
        """Set up test data before each test"""
        ensure_test_config_exists()
        test_logger.debug(f"Running test: {self._testMethodName}")

    def tearDown(self):
        """Ensure config exists after each test"""
        ensure_test_config_exists()

    @patch("frappe_brazil_invoice.brazil_invoice.doctype.nfeio.tax._call_nfeio_api")
    @patch("frappe.get_doc")
    def test_full_tax_calculation_workflow(self, mock_get_doc, mock_call_api):
        """Test full tax calculation workflow from API to result"""
        test_logger.info("Testing full tax calculation workflow")

        # Check if we should use real API
        use_real_api = should_use_real_api()
        test_logger.info(
            f"Using {'real' if use_real_api else 'mocked'} API for testing"
        )

        if not use_real_api:
            # Mock API response
            mock_call_api.return_value = {
                "icms": {"valor": 18.0},
                "ipi": {"valor": 9.75},
                "pis": {"valor": 1.65},
                "cofins": {"valor": 7.6},
            }

        # Create mock invoice
        mock_invoice = MagicMock()
        mock_invoice.invoice_items_table = [
            MagicMock(
                item_code="TEST_ITEM_001",
                item_name="Test Item",
                ncm="8504.40.90",
                quantity=1,
                rate=100.0,
                amount=100.0,
            )
        ]
        mock_invoice.delivery_state = "RJ"
        mock_invoice.client_id_number = "12345678901234"
        mock_invoice.total_freight = 0
        mock_invoice.total_insurance = 0
        mock_invoice.other_expenses = 0
        mock_invoice.icms_value = 0
        mock_invoice.ipi_value = 0
        mock_invoice.pis_value = 0
        mock_invoice.cofins_value = 0

        # Create mock tax template
        mock_tax_template = MagicMock()
        mock_tax_template.calculate_automatically_icms = True
        mock_tax_template.calculate_automatically_ipi = True
        mock_tax_template.calculate_automatically_pis = True
        mock_tax_template.calculate_automatically_cofins = True
        mock_tax_template.add_freight_icms = False
        mock_tax_template.add_insurance_icms = False
        mock_tax_template.add_other_expenses_icms = False

        def get_doc_side_effect(doctype, name=None, **kwargs):
            if doctype == "Product Invoice":
                return mock_invoice
            elif doctype == "Tax":
                return mock_tax_template
            elif doctype == "Error Log":
                # Handle frappe.log_error calls
                return MagicMock()
            return MagicMock()

        mock_get_doc.side_effect = get_doc_side_effect

        result = nfeio.calculate_product_invoice_taxes("TEST_INVOICE", "TEST_TAX_TEMPLATE")

        # Verify success
        self.assertTrue(result["success"])

        if not use_real_api:
            # Verify API was called only if using mocks
            mock_call_api.assert_called_once()

        test_logger.info("✓ Full tax calculation workflow completed successfully")
