# NFe.io Quick Reference

## 🚀 Quick Start

### Configuration
Create an NFeIO document with:
- Company ID: `your_company_id`
- API Token: `your_api_token`
- Is Test Config: `0` (for production)

## 📋 Common Operations

### Issue Invoice
```python
frappe.call(
    "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.issue_nfe",
    invoice_data={...}
)
```

### Cancel Invoice
```python
frappe.call(
    "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.cancel_nfe",
    invoice_id="nfe_abc123",
    reason="Customer request"
)
```

### Check Status
```python
frappe.call(
    "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.query_nfe_events",
    invoice_id="nfe_abc123"
)
```

### Get Documents
```python
# PDF (DANFE)
frappe.call(
    "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.get_nfe_pdf",
    invoice_id="nfe_abc123"
)

# XML
frappe.call(
    "frappe_brazil_invoice.brazil_invoice.doctype.nfeio.nfeio.get_nfe_xml",
    invoice_id="nfe_abc123"
)
```

## 🔍 Event Types

Common event types to look for:
- `Queued` - Invoice queued for processing
- `Authorized` - Invoice authorized by SEFAZ
- `Issued` - Invoice successfully issued
- `Cancelled` - Invoice cancelled
- `Rejected` - Invoice rejected (check reason)

## ⚠️ Important Notes

1. **Asynchronous Processing**: NFe.io processes requests asynchronously
   - Issue/cancel returns immediately with "Queued" status
   - Use `query_nfe_events` to check final status
   - Wait 5-10 seconds before checking status

2. **Error Handling**: All endpoints return `{"success": true/false}`
   - Check `success` field before accessing data
   - Review `error` field for failure details

3. **Rate Limits**: Be mindful of API rate limits
   - Don't poll events too frequently
   - Use webhooks for real-time updates (recommended)

## 🧪 Testing

Run tests:
```bash
bench --site dev.localhost run-tests --module \
  frappe_brazil_invoice.brazil_invoice.doctype.nfeio.test_product_invoice
```

## 📚 Full Documentation

- Implementation Guide: `PRODUCT_INVOICE_IMPLEMENTATION.md`
- Implementation Summary: `IMPLEMENTATION_SUMMARY.md`
- NFe.io API Docs: https://nfe.io/docs/desenvolvedores/rest-api/nota-fiscal-de-produto-v2/

## 🐛 Troubleshooting

| Error | Solution |
|-------|----------|
| "No valid NFe.io configuration found" | Create NFeIO document with credentials |
| "Authentication failed" | Check API token is correct |
| "Invoice ID is required" | Provide invoice_id parameter |
| "API request timed out" | Retry request or check NFe.io status |
| "Resource not found" | Verify invoice ID exists |

## 📞 Support

1. Check error logs in Frappe
2. Review NFe.io dashboard
3. Consult implementation documentation
4. Contact NFe.io support for API issues
