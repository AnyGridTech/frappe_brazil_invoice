# Copyright (c) 2025, AnyGridTech and Contributors
# See license.txt

"""
Mock Unit Tests for Tax Calculation

Tests with mocked API responses cover:
- Tax calculation functions
- API payload building
- Fallback tax calculations
- Integration with Frappe framework

To run these tests:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.nfeio.test_tax_mock

To run a specific test class:
    bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.nfeio.test_tax_mock --test TestTaxCalculation
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock
from . import tax
import logging

# Set up test logger
test_logger = logging.getLogger("tax_tests")
test_logger.setLevel(logging.INFO)


def setUpModule():
    """Set up test data once for the entire module"""
    test_logger.info("Setting up Tax Calculation test module")

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
    test_logger.info("Tearing down Tax Calculation test module")
    # We don't delete test configs - they are reused across test runs


nfe_config_test = {
    "doctype": "NFeIO",
    "config_name": "Test Tax Config",
    "company_name": "Test Company",
    "company_id": "test_company_id_123",
    "api_token": "test_api_token_tax_789",  # Different token for tax tests
    "is_test_config": 1,
    "usage_priority": 1,
}


def ensure_test_config_exists():
    """Helper to ensure test config exists"""
    # Check if a test config already exists
    existing = frappe.get_all(
        "NFeIO",
        filters={"config_name": "Test Tax Config", "is_test_config": 1},
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
    2. Then fall back to mock config with config_name='Test Tax Config'
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
        filters={"config_name": "Test Tax Config", "is_test_config": 1},
        limit=1,
    )

    if not mock_configs:
        ensure_test_config_exists()
        # After creating, get it again
        mock_configs = frappe.get_all(
            "NFeIO",
            filters={"config_name": "Test Tax Config", "is_test_config": 1},
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


class TestTaxCalculation(FrappeTestCase):
    """Test tax calculation functions"""

    def setUp(self):
        """Set up test data"""
        ensure_test_config_exists()
        test_logger.debug(f"Running test: {self._testMethodName}")

    def tearDown(self):
        """Ensure config exists after each test"""
        ensure_test_config_exists()

    def test_get_nfeio_config(self):
        """Test getting NFe.io configuration"""
        config = tax._get_nfeio_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.company_id, "test_company_id_123")
        self.assertEqual(config.api_token, "test_api_token_tax_789")

    def test_get_company_state(self):
        """Test getting company state"""
        state = tax._get_company_state()
        self.assertEqual(state, "SP")  # Default state

    def test_prepare_items_for_api(self):
        """Test preparing items for API call"""
        # Create mock invoice document
        invoice_doc = MagicMock()
        invoice_doc.invoice_items_table = [
            MagicMock(
                item_code="TEST_ITEM_001",
                item_name="Test Item 001",
                ncm="8504.40.90",
                quantity=2,
                rate=100.0,
                amount=200.0,
            ),
            MagicMock(
                item_code="TEST_ITEM_002",
                item_name="Test Item 002",
                ncm="85049090",
                quantity=1,
                rate=150.0,
                amount=150.0,
            ),
        ]

        items = tax._prepare_items_for_api(invoice_doc)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["codigo"], "TEST_ITEM_001")
        self.assertEqual(items[0]["ncm"], "85044090")
        self.assertEqual(items[0]["quantidade"], 2.0)
        self.assertEqual(items[0]["valorUnitario"], 100.0)
        self.assertEqual(items[0]["valorTotal"], 200.0)

    def test_build_api_payload(self):
        """Test building API payload"""
        # Create mock invoice and tax template
        invoice_doc = MagicMock()
        invoice_doc.delivery_state = "RJ"
        invoice_doc.client_id_number = "12345678901234"  # CNPJ (14 digits)
        invoice_doc.total_freight = 50.0
        invoice_doc.total_insurance = 25.0
        invoice_doc.other_expenses = 10.0

        tax_template = MagicMock()
        tax_template.add_freight_icms = True
        tax_template.add_insurance_icms = True
        tax_template.add_other_expenses_icms = True

        items = [
            {
                "codigo": "TEST_ITEM_001",
                "descricao": "Test Item 001",
                "ncm": "85044090",
                "quantidade": 1.0,
                "valorUnitario": 100.0,
                "valorTotal": 100.0,
            }
        ]

        payload = tax._build_api_payload(invoice_doc, tax_template, "SP", "RJ", items)

        # Check new API format
        self.assertEqual(payload["issuer"]["state"], "SP")
        self.assertEqual(payload["recipient"]["state"], "RJ")
        self.assertEqual(payload["operationType"], "Outgoing")
        self.assertEqual(len(payload["items"]), 1)
        # Check that freight/insurance/others are distributed to items
        self.assertIn("freightAmount", payload["items"][0])
        self.assertIn("insuranceAmount", payload["items"][0])
        self.assertIn("othersAmount", payload["items"][0])

    def test_build_api_payload_cpf(self):
        """Test building API payload with CPF client"""
        invoice_doc = MagicMock()
        invoice_doc.delivery_state = "RJ"
        invoice_doc.client_id_number = "12345678901"  # CPF (11 digits)
        invoice_doc.total_freight = 0
        invoice_doc.total_insurance = 0
        invoice_doc.other_expenses = 0

        tax_template = MagicMock()
        tax_template.add_freight_icms = False
        tax_template.add_insurance_icms = False
        tax_template.add_other_expenses_icms = False

        items = [
            {
                "codigo": "TEST_ITEM_001",
                "descricao": "Test Item 001",
                "ncm": "85044090",
                "quantidade": 1.0,
                "valorUnitario": 100.0,
                "valorTotal": 100.0,
            }
        ]

        payload = tax._build_api_payload(invoice_doc, tax_template, "SP", "RJ", items)

        # Check new API format structure
        self.assertEqual(payload["issuer"]["state"], "SP")
        self.assertEqual(payload["recipient"]["state"], "RJ")
        self.assertEqual(len(payload["items"]), 1)
        # Check that optional values are not in items when not configured
        self.assertNotIn("freightAmount", payload["items"][0])
        self.assertNotIn("insuranceAmount", payload["items"][0])
        self.assertNotIn("othersAmount", payload["items"][0])

    @patch("frappe_brazil_invoice.brazil_invoice.doctype.nfeio.tax.requests.post")
    def test_call_nfeio_api_success(self, mock_post):
        """Test successful API call"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "icms": {"valor": 18.0},
            "ipi": {"valor": 9.75},
            "pis": {"valor": 1.65},
            "cofins": {"valor": 7.6},
        }
        mock_post.return_value = mock_response

        payload = {"ufOrigem": "SP", "ufDestino": "RJ", "itens": []}
        result = tax._call_nfeio_api("test_api_key", "test_company_id", payload)

        self.assertIsNotNone(result)
        self.assertEqual(result["icms"]["valor"], 18.0)
        self.assertEqual(result["ipi"]["valor"], 9.75)

    @patch("frappe_brazil_invoice.brazil_invoice.doctype.nfeio.tax.requests.post")
    def test_call_nfeio_api_failure(self, mock_post):
        """Test failed API call"""
        # Mock failed API response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        payload = {"ufOrigem": "SP", "ufDestino": "RJ", "itens": []}
        result = tax._call_nfeio_api("test_api_key", "test_company_id", payload)

        self.assertIsNone(result)

    def test_update_invoice_with_tax_values(self):
        """Test updating invoice with calculated tax values"""
        # Create mock invoice and tax template
        invoice_doc = MagicMock()
        invoice_doc.icms_value = 0
        invoice_doc.ipi_value = 0
        invoice_doc.pis_value = 0
        invoice_doc.cofins_value = 0

        tax_template = MagicMock()
        tax_template.calculate_automatically_icms = True
        tax_template.calculate_automatically_ipi = True
        tax_template.calculate_automatically_pis = True
        tax_template.calculate_automatically_cofins = True

        # New API response format with items array
        result = {
            "items": [
                {
                    "icms": {"vICMS": "18.0"},
                    "ipi": {"vIPI": "9.75"},
                    "pis": {"vPIS": "1.65"},
                    "cofins": {"vCOFINS": "7.6"},
                }
            ]
        }

        tax._update_invoice_with_tax_values(invoice_doc, tax_template, result)

        self.assertEqual(invoice_doc.icms_value, 18.0)
        self.assertEqual(invoice_doc.ipi_value, 9.75)
        self.assertEqual(invoice_doc.pis_value, 1.65)
        self.assertEqual(invoice_doc.cofins_value, 7.6)

    def test_calculate_icms_fallback_interstate(self):
        """Test ICMS fallback calculation for interstate operation"""
        invoice_doc = MagicMock()
        invoice_doc.invoice_items_table = [
            MagicMock(amount=100.0),
            MagicMock(amount=200.0),
        ]
        invoice_doc.total_freight = 0
        invoice_doc.total_insurance = 0
        invoice_doc.other_expenses = 0
        invoice_doc.delivery_state = "RJ"  # Different from SP, so interstate
        invoice_doc.icms_value = 0

        tax_template = MagicMock()
        tax_template.add_freight_icms = False
        tax_template.add_insurance_icms = False
        tax_template.add_other_expenses_icms = False

        tax._calculate_icms_fallback(invoice_doc, tax_template, is_interstate=True)

        # Interstate rate is 12%: 300 * 0.12 = 36
        self.assertEqual(invoice_doc.icms_value, 36.0)

    def test_calculate_icms_fallback_intrastate(self):
        """Test ICMS fallback calculation for intrastate operation"""
        invoice_doc = MagicMock()
        invoice_doc.invoice_items_table = [
            MagicMock(amount=100.0),
            MagicMock(amount=200.0),
        ]
        invoice_doc.total_freight = 0
        invoice_doc.total_insurance = 0
        invoice_doc.other_expenses = 0
        invoice_doc.icms_value = 0

        tax_template = MagicMock()
        tax_template.add_freight_icms = False
        tax_template.add_insurance_icms = False
        tax_template.add_other_expenses_icms = False

        tax._calculate_icms_fallback(invoice_doc, tax_template, is_interstate=False)

        # Intrastate rate is 18%: 300 * 0.18 = 54
        self.assertEqual(invoice_doc.icms_value, 54.0)

    def test_calculate_ipi_fallback(self):
        """Test IPI fallback calculation"""
        invoice_doc = MagicMock()
        invoice_doc.invoice_items_table = [
            MagicMock(amount=100.0, ncm="8504.40.90"),  # 9.75% rate
            MagicMock(amount=200.0, ncm="8504.90.90"),  # 6.50% rate
        ]
        invoice_doc.ipi_value = 0

        tax_template = MagicMock()

        tax._calculate_ipi_fallback(invoice_doc, tax_template)

        # IPI: (100 * 0.0975) + (200 * 0.065) = 9.75 + 13.00 = 22.75
        self.assertEqual(invoice_doc.ipi_value, 22.75)

    @patch("frappe_brazil_invoice.brazil_invoice.doctype.nfeio.tax._get_nfeio_config")
    @patch("frappe_brazil_invoice.brazil_invoice.doctype.nfeio.tax._call_nfeio_api")
    def test_calculate_taxes_success(self, mock_call_api, mock_get_config):
        """Test successful tax calculation"""
        # Mock NFe.io config
        mock_config = MagicMock()
        mock_config.api_token = "test_token"
        mock_config.company_id = "test_company"
        mock_get_config.return_value = mock_config

        # Mock API response with new format
        mock_call_api.return_value = {
            "items": [
                {
                    "icms": {"vICMS": "18.0"},
                    "ipi": {"vIPI": "9.75"},
                    "pis": {"vPIS": "1.65"},
                    "cofins": {"vCOFINS": "7.6"},
                }
            ]
        }

        # Create mock invoice and tax template
        invoice_doc = MagicMock()
        invoice_doc.invoice_items_table = [
            MagicMock(
                item_code="TEST_ITEM_001",
                item_name="Test Item",
                ncm="8504.40.90",
                quantity=1,
                rate=100.0,
                amount=100.0,
            )
        ]
        invoice_doc.delivery_state = "RJ"
        invoice_doc.client_id_number = "12345678901234"
        invoice_doc.total_freight = 0
        invoice_doc.total_insurance = 0
        invoice_doc.other_expenses = 0
        invoice_doc.icms_value = 0
        invoice_doc.ipi_value = 0
        invoice_doc.pis_value = 0
        invoice_doc.cofins_value = 0

        tax_template = MagicMock()
        tax_template.calculate_automatically_icms = True
        tax_template.calculate_automatically_ipi = True
        tax_template.calculate_automatically_pis = True
        tax_template.calculate_automatically_cofins = True
        tax_template.add_freight_icms = False
        tax_template.add_insurance_icms = False
        tax_template.add_other_expenses_icms = False

        tax.calculate_taxes(invoice_doc)

        self.assertEqual(invoice_doc.icms_value, 18.0)
        self.assertEqual(invoice_doc.ipi_value, 9.75)
        self.assertEqual(invoice_doc.pis_value, 1.65)
        self.assertEqual(invoice_doc.cofins_value, 7.6)

    @patch("frappe_brazil_invoice.brazil_invoice.doctype.nfeio.tax._get_nfeio_config")
    def test_calculate_taxes_no_config(self, mock_get_config):
        """Test tax calculation with no NFe.io configuration"""
        # Mock no config
        mock_get_config.return_value = None

        # Create mock invoice and tax template
        invoice_doc = MagicMock()
        invoice_doc.invoice_items_table = [
            MagicMock(
                item_code="TEST_ITEM_001",
                item_name="Test Item",
                ncm="8504.40.90",
                quantity=1,
                rate=100.0,
                amount=100.0,
            )
        ]
        invoice_doc.delivery_state = "SP"
        invoice_doc.icms_value = 0
        invoice_doc.ipi_value = 0

        tax_template = MagicMock()
        tax_template.calculate_automatically_icms = True
        tax_template.calculate_automatically_ipi = True
        tax_template.add_freight_icms = False
        tax_template.add_insurance_icms = False
        tax_template.add_other_expenses_icms = False

        # Should fall back to hardcoded calculation when use_fallback=True
        tax.calculate_taxes(invoice_doc, use_fallback=True)

        # Verify fallback was used (IPI: 100 * 0.0975 = 9.75)
        self.assertEqual(invoice_doc.ipi_value, 9.75)
        # ICMS intrastate: 100 * 0.18 = 18.0
        self.assertEqual(invoice_doc.icms_value, 18.0)


class TestTaxCalculationFallback(FrappeTestCase):
    """Test fallback tax calculation"""

    def test_calculate_taxes_fallback_all_taxes(self):
        """Test fallback calculation for all taxes"""
        invoice_doc = MagicMock()
        invoice_doc.invoice_items_table = [
            MagicMock(amount=100.0, ncm="8504.40.90"),
        ]
        invoice_doc.delivery_state = "RJ"  # Interstate
        invoice_doc.total_freight = 0
        invoice_doc.total_insurance = 0
        invoice_doc.other_expenses = 0
        invoice_doc.icms_value = 0
        invoice_doc.ipi_value = 0

        tax_template = MagicMock()
        tax_template.calculate_automatically_icms = True
        tax_template.calculate_automatically_ipi = True
        tax_template.add_freight_icms = False
        tax_template.add_insurance_icms = False
        tax_template.add_other_expenses_icms = False

        tax.calculate_taxes_fallback(invoice_doc, tax_template)

        # ICMS interstate: 100 * 0.12 = 12.0
        self.assertEqual(invoice_doc.icms_value, 12.0)
        # IPI: 100 * 0.0975 = 9.75
        self.assertEqual(invoice_doc.ipi_value, 9.75)

    def test_calculate_taxes_fallback_no_items(self):
        """Test fallback calculation with no items"""
        invoice_doc = MagicMock()
        invoice_doc.invoice_items_table = []

        tax_template = MagicMock()

        # Should not raise any errors
        tax.calculate_taxes_fallback(invoice_doc, tax_template)
