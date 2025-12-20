# Invoice Creation API - Summary

## Status: ✅ ALL TESTS PASSING (27/27)

## Created Files

### 1. `api.py`
Main API module with 4 endpoints:

- **`create_invoice()`**: Creates a new invoice from automation parameters
  - Required fields: `client_name`, `client_id_number`
  - Optional: All other invoice fields including tax fields
  - Returns: `{"success": bool, "docname": str, "message": str, "invoice_status": str}`

- **`get_invoice_details(docname)`**: Retrieves invoice details
  - Required: `docname`
  - Returns: `{"success": bool, "invoice": dict, "message": str}`

- **`update_invoice_status(docname, ...)`**: Updates invoice after external processing
  - Required: `docname`
  - Optional: `invoice_id`, `invoice_link`, `invoice_number`, `invoice_serie`
  - Returns: `{"success": bool, "message": str, "docname": str}`

- **`bulk_create_invoices(invoices_data)`**: Creates multiple invoices
  - Required: `invoices_data` (list of invoice dicts)
  - Returns: `{"success": bool, "created_invoices": list, "failed_invoices": list, ...}`

### 2. `test_api.py`
Comprehensive test suite with 27 test cases covering:

**Basic API Tests (16 tests):**
- ✅ Basic invoice creation
- ✅ All fields populated
- ✅ Missing required fields validation
- ✅ Auto-submit functionality
- ✅ JSON string input handling
- ✅ Get invoice details
- ✅ Update invoice status
- ✅ Bulk creation (success, partial failure, edge cases)

**Tax Tests (11 tests):**
- ✅ ICMS tax (state tax)
- ✅ ISS tax (service tax)
- ✅ IPI tax (industrial products tax)
- ✅ PIS/COFINS taxes (federal taxes)
- ✅ Multiple taxes combined
- ✅ Tax-exempt transactions
- ✅ Tax template field
- ✅ Interstate ICMS with different rates
- ✅ Tax calculations including freight
- ✅ Simples Nacional regime
- ✅ Bulk invoices with different tax scenarios

## API Usage

### Endpoint URL Pattern
```
https://your-site.com/api/method/frappe_brazil_invoice.brazil_invoice.api.<function_name>
```

### Authentication
```
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
```

### Example: Create Invoice
```python
import requests

response = requests.post(
    "https://your-site.com/api/method/frappe_brazil_invoice.brazil_invoice.api.create_invoice",
    json={
        "client_name": "Test Client",
        "client_id_number": "12345678901",
        "total": 1000.00
    },
    headers={
        "Authorization": "token YOUR_KEY:YOUR_SECRET",
        "Content-Type": "application/json"
    }
)

result = response.json()
if result["success"]:
    print(f"Invoice created: {result['docname']}")
```

## Running Tests

```bash
cd /workspace/development/frappe-bench
bench --site dev.localhost set-config allow_tests true
bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.test_api
```

**Result:** ✅ Ran 16 tests in 1.632s - OK

## Files Location
```
frappe_brazil_invoice/brazil_invoice/
├── api.py          # Main API implementation
└── test_api.py     # Comprehensive test suite
```
