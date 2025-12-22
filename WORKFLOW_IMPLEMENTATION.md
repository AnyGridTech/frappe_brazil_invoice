# Invoice Workflow Implementation

## Overview
Implemented a complete workflow system for the Invoices doctype with multiple states and transition paths to handle the Brazilian NFe invoice lifecycle.

## Workflow States

The following workflow states have been defined:

1. **Created** (Info/Blue) - Initial state when invoice is created
2. **Processing** (Warning/Orange) - Invoice is being processed by NFe.io/SEFAZ
3. **Contingency** (Warning/Orange) - SEFAZ offline, invoice in contingency mode (FS-DA)
4. **Submitted** (Success/Green) - Invoice successfully authorized and submitted
5. **Rejected** (Danger/Red) - Invoice rejected by SEFAZ
6. **Cancelled** (Danger/Red) - Invoice cancelled
7. **Unused** (Inverse/Black) - Invoice marked as unused/void

## Workflow Transitions

The system supports the following workflow paths:

### Path 1: Successful Processing
```
Created → Processing → Submitted
```
- Normal flow when everything works correctly
- Invoice gets authorized by SEFAZ and submitted

### Path 2: Rejection
```
Created → Processing → Rejected
```
- Invoice rejected by SEFAZ due to validation errors
- Common reasons: Invalid CPF/CNPJ, tax calculation errors, missing required fields

### Path 3: Contingency Mode
```
Created → Processing → Contingency → Submitted
```
- SEFAZ temporarily unavailable
- Invoice issued in contingency mode (FS-DA)
- Later transmitted when SEFAZ comes back online

### Path 4: Unused
```
Created → Processing → Unused
```
- Invoice not needed (e.g., client cancelled order)
- Marked as unused to maintain audit trail
- Alternative: `Created → Unused` (direct path)

## Files Created

### 1. Fixtures Directory
`/frappe_brazil_invoice/fixtures/`

#### workflow_state.json
Defines all 7 workflow states with their visual styling (icons and colors).

#### workflow_action_master.json
Defines available actions:
- Process
- Submit
- Reject
- Move to Contingency
- Mark as Unused
- Cancel

#### workflow.json
Defines the complete "Invoice Workflow" including:
- Document type: Invoices
- All state definitions with docstatus mapping
- All allowed transitions between states
- Role-based permissions (System Manager)

### 2. Updated Files

#### hooks.py
Added fixtures configuration to load workflow data during app installation:
```python
fixtures = [
    {"dt": "Workflow State", "filters": [...]},
    {"dt": "Workflow Action Master", "filters": [...]},
    {"dt": "Workflow", "filters": [...]}
]
```

#### invoices.json
Added new fields to the Invoices doctype:
- `invoice_status` - Link to Workflow State (read-only, managed by workflow)
- `status_reason` - Small Text field to track reason for current status
- `column_break_status` - Column break for form layout

Updated field_order to include new status fields at the top of the form.

### 3. Test File

#### test_invoices.py
Added comprehensive test class `TestInvoiceWorkflowStatuses` with tests for:

1. **test_workflow_created_to_processing_to_submitted** - Normal success flow
2. **test_workflow_created_to_processing_to_rejected** - Rejection scenario
3. **test_workflow_created_to_processing_to_contingency_to_submitted** - Contingency mode
4. **test_workflow_created_to_processing_to_unused** - Marking as unused
5. **test_workflow_status_with_complete_invoice_lifecycle** - Complete lifecycle with all details
6. **test_bulk_invoices_with_different_statuses** - Bulk test with 4 different end states
7. **test_status_reason_field_updates** - Status reason tracking

## Installation

To install and activate the workflow:

```bash
# Navigate to your bench directory
cd /workspace/development/frappe-bench

# Install the app (if not already installed)
bench --site dev.localhost install-app frappe_brazil_invoice

# Or if app is already installed, export and import fixtures
bench --site dev.localhost export-fixtures

# Migrate to add new fields
bench --site dev.localhost migrate

# Clear cache
bench --site dev.localhost clear-cache

# Restart
bench restart
```

## Usage in Code

### Setting Invoice Status Programmatically

```python
import frappe

# Get invoice
invoice = frappe.get_doc("Invoices", "INV-2025-0001")

# Update status
invoice.invoice_status = "Processing"
invoice.status_reason = "Sent to NFe.io for validation"
invoice.save()

# Or for submission
invoice.invoice_status = "Submitted"
invoice.status_reason = "NFe approved - Number: 000123, Serie: 1"
invoice.submit()
frappe.db.commit()
```

### Checking Current Status

```python
invoice = frappe.get_doc("Invoices", "INV-2025-0001")
current_status = invoice.invoice_status  # Returns: "Created", "Processing", etc.
status_reason = invoice.status_reason   # Returns reason text
```

## Workflow Benefits

1. **Audit Trail** - Complete history of invoice state changes
2. **Status Tracking** - Clear visibility of invoice processing status
3. **Error Handling** - Proper handling of rejections and contingency scenarios
4. **Role-Based Control** - Workflow actions restricted to authorized roles
5. **Integration Ready** - Designed for NFe.io/SEFAZ integration
6. **Compliance** - Supports Brazilian NFe regulations including contingency mode

## Future Enhancements

Potential improvements:
- Email notifications on status changes
- Automatic status updates from NFe.io webhooks
- Workflow analytics dashboard
- Additional roles for different workflow actions
- Time-based auto-transitions (e.g., auto-reject after X hours in Processing)

## Testing

Run the workflow tests:

```bash
# Run all invoice tests
bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.invoices.test_invoices

# Run only workflow status tests
bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.invoices.test_invoices --test TestInvoiceWorkflowStatuses

# Run specific test
bench --site dev.localhost run-tests --module frappe_brazil_invoice.brazil_invoice.doctype.invoices.test_invoices --test TestInvoiceWorkflowStatuses.test_workflow_created_to_processing_to_submitted
```

## Notes

- The `invoice_status` field is set as read-only in the form but can be updated programmatically
- The `status_reason` field is editable to allow detailed tracking of status changes
- All workflow transitions respect Frappe's docstatus values (0=Draft, 1=Submitted, 2=Cancelled)
- The workflow is configured for "System Manager" role but can be extended to other roles as needed
