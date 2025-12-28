# NFe.io Product Invoice Integration - Implementation Guide

## Overview

This implementation provides a complete integration with NFe.io API for managing product invoices (NFe - Nota Fiscal Eletrônica) in Brazil. It includes operations for issuing, canceling, and querying invoices, as well as retrieving PDF (DANFE) and XML documents.

## API Documentation References

- **Introduction**: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/nota-fiscal-de-produto/
- **Issue Invoice**: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/emitir-uma-nota-fiscal-eletronica-nfe/
- **Cancel Invoice**: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/cancelar-uma-nota-fiscal-eletronica-nfe/
- **Query Events**: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/consultar-eventos-por-id-uma-nota-fiscal-eletronica-nfe/
- **Get PDF**: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/consultar-pdf-do-documento-auxiliar-da-nota-fiscal-eletronica-danfe/
- **Get XML**: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/consultar-xml-da-nota-fiscal-eletronica-nfe/

## Architecture

### Files Structure

```
frappe_brazil_invoice/brazil_invoice/doctype/nfeio/
├── nfeio.py                    # Whitelisted API endpoints
├── product_invoice.py          # Core NFe.io operations
└── test_product_invoice.py     # Comprehensive test suite
```

### Components

1. **product_invoice.py**: Core module with NFe.io API operations
2. **nfeio.py**: Frappe whitelisted endpoints for frontend/API access
3. **test_product_invoice.py**: Unit and integration tests

## Features

### 1. Issue Product Invoice (NFe)

**Endpoint**: `frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.issue_nfe`

Issues a product invoice to the NFe.io queue for asynchronous processing.

**Parameters**:
- `invoice_data`: Complete invoice data in NFe.io format

**Returns**:
```json
{
  "success": true,
  "data": {
    "id": "nfe_abc123xyz",
    "status": "Queued",
    "number": 1001
  },
  "message": "Invoice queued for emission successfully"
}
```

**Example Usage**:
```python
# From Python
result = frappe.call(
    "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.issue_nfe",
    invoice_data={
        "operationNature": "VENDA",
        "operationType": "Outgoing",
        "consumerType": "FinalConsumer",
        "buyer": {
            "name": "Customer Name",
            "federalTaxNumber": 12345678901234
        },
        "items": [
            {
                "code": "PROD001",
                "description": "Product Name",
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
)
```

```javascript
// From JavaScript
frappe.call({
    method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.issue_nfe",
    args: {
        invoice_data: invoiceDataObject
    },
    callback: function(r) {
        if (r.message.success) {
            console.log("Invoice issued:", r.message.data.id);
        }
    }
});
```

### 2. Cancel Product Invoice (NFe)

**Endpoint**: `frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.cancel_nfe`

Cancels a previously issued product invoice.

**Parameters**:
- `invoice_id`: NFe.io invoice ID
- `reason`: Cancellation reason (required)

**Returns**:
```json
{
  "success": true,
  "data": {
    "success": true,
    "message": "Cancellation queued"
  },
  "message": "Invoice cancellation queued successfully"
}
```

**Example Usage**:
```python
# From Python
result = frappe.call(
    "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.cancel_nfe",
    invoice_id="nfe_abc123xyz",
    reason="Customer requested cancellation"
)
```

```javascript
// From JavaScript
frappe.call({
    method: "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.cancel_nfe",
    args: {
        invoice_id: "nfe_abc123xyz",
        reason: "Customer requested cancellation"
    },
    callback: function(r) {
        if (r.message.success) {
            frappe.msgprint("Invoice cancellation queued");
        }
    }
});
```

### 3. Query Invoice Events

**Endpoint**: `frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.query_nfe_events`

Retrieves event history for an invoice to track processing status.

**Parameters**:
- `invoice_id`: NFe.io invoice ID
- `limit`: Maximum events to retrieve (default: 10)
- `starting_after`: Pagination start index (default: 0)

**Returns**:
```json
{
  "success": true,
  "data": {
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
    "hasMore": false
  }
}
```

**Example Usage**:
```python
# From Python
result = frappe.call(
    "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.query_nfe_events",
    invoice_id="nfe_abc123xyz",
    limit=20
)
```

### 4. Get Invoice PDF (DANFE)

**Endpoint**: `frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.get_nfe_pdf`

Retrieves the URL to download the DANFE (Documento Auxiliar da Nota Fiscal Eletrônica) PDF.

**Parameters**:
- `invoice_id`: NFe.io invoice ID
- `force`: Force PDF generation (default: False)

**Returns**:
```json
{
  "success": true,
  "data": {
    "uri": "https://api.nfse.io/documents/nfe_abc123xyz.pdf"
  },
  "pdf_url": "https://api.nfse.io/documents/nfe_abc123xyz.pdf"
}
```

**Example Usage**:
```python
# From Python
result = frappe.call(
    "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.get_nfe_pdf",
    invoice_id="nfe_abc123xyz",
    force=True
)
pdf_url = result["pdf_url"]
```

### 5. Get Invoice XML

**Endpoint**: `frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.get_nfe_xml`

Retrieves the URL to download the official NFe XML document.

**Parameters**:
- `invoice_id`: NFe.io invoice ID

**Returns**:
```json
{
  "success": true,
  "data": {
    "uri": "https://api.nfse.io/documents/nfe_abc123xyz.xml"
  },
  "xml_url": "https://api.nfse.io/documents/nfe_abc123xyz.xml"
}
```

**Example Usage**:
```python
# From Python
result = frappe.call(
    "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.get_nfe_xml",
    invoice_id="nfe_abc123xyz"
)
xml_url = result["xml_url"]
```

### 6. Build NFe from Product Invoice

**Endpoint**: `frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.build_nfe_from_invoice`

Converts a Frappe Product Invoice document to NFe.io API format.

**Parameters**:
- `invoice_name`: Name of the Product Invoice document

**Returns**:
```json
{
  "success": true,
  "data": {
    "operationNature": "VENDA",
    "operationType": "Outgoing",
    "buyer": {...},
    "items": [...],
    "totals": {...}
  }
}
```

## Configuration

### NFe.io Settings

The NFeIO doctype must be configured with:

- **Company ID**: Your NFe.io company identifier
- **Company Name**: Company name for reference
- **API Token**: Authentication token from NFe.io
- **Is Test Config**: Set to 0 for production use

Only configurations with `is_test_config = 0` are used by the API.

## Error Handling

All endpoints return a standardized error response:

```json
{
  "success": false,
  "error": "Error message description"
}
```

### Common Errors

1. **Missing Configuration**:
   - Error: "No valid NFe.io configuration found"
   - Solution: Create NFeIO document with API credentials

2. **Invalid API Token**:
   - Error: "Authentication failed - Invalid API token"
   - Solution: Verify API token in NFe.io settings

3. **Missing Required Parameters**:
   - Error: "Invoice ID is required" / "Cancellation reason is required"
   - Solution: Provide all required parameters

4. **API Timeout**:
   - Error: "API request timed out"
   - Solution: Retry the request or check NFe.io service status

5. **Resource Not Found**:
   - Error: "Resource not found"
   - Solution: Verify invoice ID exists in NFe.io

## Asynchronous Processing

**Important**: NFe.io processes invoices asynchronously. When you issue or cancel an invoice:

1. The API returns immediately with a queued status
2. NFe.io processes the request in the background
3. Use webhooks or `query_nfe_events` to track the actual status

### Recommended Workflow

```python
# 1. Issue invoice
issue_result = frappe.call("...issue_nfe", invoice_data=data)
invoice_id = issue_result["data"]["id"]

# 2. Wait a few seconds
import time
time.sleep(5)

# 3. Query events to check status
events_result = frappe.call("...query_nfe_events", invoice_id=invoice_id)
events = events_result["data"]["events"]

# 4. Check for authorization
for event in events:
    if event["type"] == "Authorized":
        print("Invoice authorized!")
        break
```

## Testing

The implementation includes comprehensive tests covering:

- Successful operations
- Error scenarios
- API timeouts and connection errors
- Missing parameters
- Authentication failures
- Pagination
- Payload building

### Running Tests

```bash
cd /workspace/development/frappe-bench
bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.nfeio.test_product_invoice
```

### Test Coverage

- 21 unit tests
- 100% function coverage
- Mock-based testing (no actual API calls)
- Integration tests with Frappe framework

## Security Considerations

1. **API Token Storage**: Store API tokens securely in the NFeIO doctype
2. **Access Control**: Whitelisted endpoints are accessible via API, ensure proper permissions
3. **Data Validation**: All inputs are validated before API calls
4. **Error Logging**: Failed operations are logged with full context

## Performance

- HTTP timeout: 30 seconds per request
- Supports pagination for large event lists
- Minimal memory footprint
- Efficient JSON serialization

## Extending the Implementation

### Custom Invoice Payload

The `build_invoice_payload` function can be extended to map your Product Invoice fields:

```python
def build_invoice_payload(invoice_doc):
    payload = {
        "operationNature": invoice_doc.operation_nature,
        "operationType": invoice_doc.operation_type,
        # Add your custom mappings here
        "buyer": {
            "name": invoice_doc.customer_name,
            "federalTaxNumber": invoice_doc.customer_tax_id,
            "email": invoice_doc.customer_email,
            # Add more fields as needed
        },
        # ... rest of the payload
    }
    return payload
```

### Webhooks Integration

To receive real-time updates from NFe.io:

1. Configure webhooks in NFe.io dashboard
2. Create a webhook handler in your Frappe app
3. Process invoice status updates automatically

## Troubleshooting

### Issue: "No valid NFe.io configuration found"

**Solution**: Create an NFeIO document:
1. Go to NFeIO list
2. Create new document
3. Fill in Company ID, Company Name, and API Token
4. Set "Is Test Config" to 0
5. Save

### Issue: API requests fail with timeout

**Possible causes**:
- NFe.io service is slow or down
- Network connectivity issues
- Firewall blocking outbound HTTPS

**Solutions**:
- Check NFe.io service status
- Verify network connectivity
- Review firewall rules for api.nfse.io

### Issue: Invoice not found when querying

**Possible causes**:
- Invoice ID is incorrect
- Invoice was deleted
- Wrong company ID in configuration

**Solutions**:
- Verify invoice ID from issue response
- Check NFe.io dashboard for invoice
- Confirm company ID matches

## Support

For issues specific to:
- **NFe.io API**: Contact NFe.io support
- **This Implementation**: Review code comments and tests
- **Frappe Integration**: Consult Frappe documentation

## License

Copyright (c) 2025, AnyGridTech
See license.txt for license information
