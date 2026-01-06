# Items Implementation in Invoice Tests

## Summary

Successfully implemented complete Item doctype integration in invoice tests. Items are now properly created with all necessary fields and linked to invoices.

## Changes Made

### 1. Item Creation Helper Function

Added `create_test_item()` helper function that:
- Creates items in the Item master doctype
- Sets item_code, item_name, rate, and description
- Includes NCM (tax classification) codes
- Prevents duplicate creation (checks if item exists first)
- Returns the created item document

```python
def create_test_item(item_code, item_name, rate, ncm_code, description=None, item_group="Products"):
    """Helper function to create a test item"""
    if frappe.db.exists("Item", item_code):
        return frappe.get_doc("Item", item_code)
    
    item = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_name,
        "item_group": item_group,
        "stock_uom": "Unit",
        "is_stock_item": 1,
        "valuation_rate": rate,
        "standard_rate": rate,
        "description": description or item_name
    })
    item.insert(ignore_permissions=True)
    frappe.db.commit()
    return item
```

### 2. Updated Test Setup

Enhanced `TestInvoiceScenarios` class:
- Added `cleanup_test_items()` method to remove test items before tests
- Items are cleaned up in `setUp()` to ensure clean state
- Database rollback in `tearDown()` maintains test isolation

### 3. Complete Item Data in Tests

All invoice scenario tests now create real items with:

#### Sales Invoice Test
- **TEST-NOTEBOOK-001**: Notebook Dell Inspiron 15 (NCM: 8471.30.12)
- **TEST-MOUSE-002**: Mouse Logitech MX Master 3 (NCM: 8471.60.52)
- **TEST-KEYBOARD-003**: Teclado Mecânico Keychron K8 (NCM: 8471.60.53)

#### Warranty Repair Test
- **TEST-REPAIR-001**: Serviço de Reparo - Notebook (NCM: 8471.30.12)
- Rate: R$ 0.00 (warranty repair - no charge)

#### Exchange/Return Test
- **TEST-PHONE-EXCHANGE**: Smartphone Samsung Galaxy S23 (NCM: 8517.12.31)
- Rate: R$ 3,500.00

#### Interstate Sales Test
- **TEST-TABLET-001**: Tablet Samsung Galaxy Tab S9 (NCM: 8471.30.19)
- **TEST-MONITOR-001**: Monitor LG UltraWide 34" (NCM: 8528.59.20)

#### Bulk Sales Test
- **TEST-BULK-PROD-001**: Produto em Lote 1 (NCM: 8471.30.12)
- **TEST-BULK-PROD-002**: Produto em Lote 2 (NCM: 8471.30.12)
- **TEST-BULK-PROD-003**: Produto em Lote 3 (NCM: 8471.30.12)

#### Interstate Multiple Carriers Test
- **TEST-TV-001**: Smart TV LG 55" 4K UHD (NCM: 8528.72.00)
- **TEST-SOUNDBAR-001**: Soundbar Samsung HW-Q60T (NCM: 8518.22.00)

### 4. Invoice Item Structure

Each item in `invoices_table` now includes:
- `item_code`: Reference to Item master
- `item_name`: Item display name
- `description`: Detailed product description
- `quantity`: Number of units
- `rate`: Unit price in BRL
- `amount`: Total amount (quantity × rate)
- `ncm`: Brazilian tax classification code

## NCM Codes Used

Brazilian NCM (Nomenclatura Comum do Mercosul) codes included:
- **8471.30.12**: Portable computers (notebooks, laptops)
- **8471.30.19**: Tablets and similar devices
- **8471.60.52**: Computer mice
- **8471.60.53**: Computer keyboards
- **8517.12.31**: Smartphones
- **8528.59.20**: Computer monitors
- **8528.72.00**: Smart TVs
- **8518.22.00**: Audio equipment (soundbars)

## Test Results

All 45 tests passing:
- ✅ 42 tests executed successfully
- ✅ 3 tests skipped (as designed)
- ✅ 0 failures
- ✅ 0 errors

### Tests with Submitted Invoices

The following tests now create complete invoices with items and submit them:

1. **test_sales_invoice_with_carrier_submitted**
   - Creates 3 items (notebook, mouse, keyboard)
   - Total: R$ 9,150.00 (with freight and discount)
   - Status: Submitted (docstatus=1)

2. **test_warranty_repair_invoice_submitted**
   - Creates 1 repair service item
   - Total: R$ 0.00 (warranty repair)
   - Status: Submitted (docstatus=1)

3. **test_exchange_return_invoice_submitted**
   - Creates 1 return item (smartphone)
   - Total: R$ 3,550.00
   - Status: Submitted (docstatus=1)

4. **test_interstate_sales_with_multiple_carriers_submitted**
   - Creates 2 items (TV, soundbar)
   - Total: R$ 18,450.00
   - Status: Submitted (docstatus=1)

5. **test_bulk_sales_invoices_with_carriers_submitted**
   - Creates 3 items and 3 separate invoices
   - Each invoice submitted successfully
   - Status: All submitted (docstatus=1)

## Verification

Items can be verified in the database:

```python
# Check created items
frappe.get_all("Item", filters={"item_code": ["like", "TEST-%"]})

# Check invoice items
invoice = frappe.get_doc("Invoices", "INV-2025-XXXX")
for item in invoice.invoices_table:
    print(f"{item.item_code}: {item.item_name} - Qty: {item.quantity} × R$ {item.rate}")
```

## Benefits

1. **Real Data**: Tests now use actual Item records, matching production behavior
2. **Complete Information**: Items include names, descriptions, rates, and NCM codes
3. **Traceability**: Can track which items are used in which invoices
4. **Tax Compliance**: NCM codes enable proper Brazilian tax calculations
5. **Better Coverage**: Tests now validate the full item-to-invoice flow

## Next Steps

Consider adding:
- Custom fields for additional Brazilian tax attributes (CEST, CFOP)
- Item unit conversions (kg, m², etc.)
- Item tax templates for automatic tax calculation
- Inventory tracking integration
- Serial number/batch tracking for specific items
