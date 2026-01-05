import frappe


def _not_in_processing_status(invoice_doc):
    frappe.logger().info(
        "Product Invoice {} is not in Processing status. Current status: {}".format(
            invoice_doc.name, invoice_doc.invoice_status
        )
    )
    return invoice_doc.invoice_status != "Processing"


def _get_events_from_invoice(invoice_doc, is_test_invoice=0, nfeio_config_name=None):
    from frappe_brazil_invoice.brazil_invoice.doctype.nfeio import nfeio

    resp = nfeio.query_product_invoice_events(
        invoice_doc.invoice_id, 
        limit=15, 
        is_test_invoice=is_test_invoice,
        nfeio_config_name=nfeio_config_name
    )
    if not resp.get("success"):
        frappe.logger().error(
            "Failed to query events for NFe.io invoice ID ({}) with error: {}".format(
                invoice_doc.invoice_id, resp.get("error")
            )
        )
        return resp.get("error")
    return resp.get("data")

def _get_error_from_events(invoice_doc, data=None, nfeio_config_name=None):
    if not data:
        is_test_invoice = getattr(invoice_doc, 'is_test_invoice', 0)
        data = _get_events_from_invoice(invoice_doc, is_test_invoice, nfeio_config_name)
    if not data:
        return f"Could not retrieve events for invoice {invoice_doc.invoice_id}. Error: {data}"
    if not data.get("events"):
        return "No events found to extract error message."
    events = data.get("events", [])
    events_length = len(events)
    if events_length == 0:
        return "Events returned as empty."
    # Start from the latest event
    for i in range(events_length - 1, -1, -1):
        event = events[i]
        if event.get("type") != "Error":
            continue
        if event.get("data", {}).get("message"):
            return event.get("data").get("message")
    return "No error message found in events."

def _make_json_prettier(json_data):
    if json_data and isinstance(json_data, dict):
        import json

        return json.dumps(
            json_data, indent=2, ensure_ascii=False
        )
    return str(json_data)


@frappe.whitelist()
def handle_invoice_status_update(data):
    """
    Handle webhook calls from NFe.io for invoice status updates.
    """
    try:
        invoice_id = data.get("id")

        from frappe_brazil_invoice.brazil_invoice.doctype.nfeio import nfeio

        # Find the Product Invoice document by invoice_id to get is_test_invoice and nfeio_config
        is_test_invoice = 0
        nfeio_config_name = None
        try:
            invoice_docs = frappe.get_all(
                "Product Invoice",
                filters={"invoice_id": invoice_id},
                fields=["name", "is_test_invoice", "nfeio_config"],
                limit=1
            )
            if invoice_docs:
                is_test_invoice = invoice_docs[0].get("is_test_invoice", 0)
                nfeio_config_name = invoice_docs[0].get("nfeio_config")
        except Exception as e:
            frappe.logger().warning(f"Could not find Product Invoice for invoice_id {invoice_id}: {str(e)}")
        
        resp = nfeio.get_product_invoice_by_id(
            invoice_id, 
            is_test_invoice=is_test_invoice,
            nfeio_config_name=nfeio_config_name
        )

        if not resp.get("success"):
            frappe.logger().error(
                "Failed to retrieve invoice data for NFe.io ID {}: {}".format(
                    invoice_id, resp.get("error")
                )
            )
            return

        nfeio_invoice = resp.get("data", {})

        invoice_status = nfeio_invoice.get("status")

        if not invoice_status:
            frappe.logger().error(
                "No status found in NFe.io invoice data for ID: {}".format(invoice_id)
            )
            frappe.logger().error(f"Invoice data: {nfeio_invoice}")
            return

        if invoice_status in ["Issued", "IssuedContingency"]:
            handle_invoice_issued_status(data)
        elif invoice_status == "Error":
            handle_invoice_error_status(data)
        else:
            frappe.logger().info(
                "No action taken for invoice ID {} with status {}".format(
                    invoice_id, invoice_status
                )
            )

    except Exception as e:
        frappe.log_error(
            f"Error processing invoice status webhook for NFe.io ID {invoice_id}: {str(e)}\n{frappe.get_traceback()}",
            "Invoice Status Webhook Error",
        )


@frappe.whitelist()
def handle_invoice_issued_status(data):
    """
    Handle webhook calls from NFe.io for invoice issued status.
    """
    try:
        invoice_id = data.get("id")
        print(f"\n📋 handle_invoice_issued_status called for invoice_id: {invoice_id}")
        
        invoice_doc = frappe.get_doc("Product Invoice", {"invoice_id": invoice_id})

        if not invoice_doc:
            print(f"   ❌ No Product Invoice found for NFe.io ID: {invoice_id}")
            frappe.logger().error(
                "No Product Invoice found for NFe.io ID: {}".format(invoice_id)
            )
            return

        print(f"   ✓ Found Product Invoice: {invoice_doc.name}, Status: {invoice_doc.invoice_status}")
        
        if _not_in_processing_status(invoice_doc):
            print(f"   ⚠️ Invoice not in Processing status, skipping update")
            return
        
        print(f"   ✓ Invoice in Processing status, proceeding with update")

        from frappe_brazil_invoice.brazil_invoice.doctype.nfeio import nfeio

        invoice_id = data.get("id")
        
        # Get is_test_invoice flag and nfeio_config from the Product Invoice document
        is_test_invoice = getattr(invoice_doc, 'is_test_invoice', 0)
        nfeio_config_name = getattr(invoice_doc, 'nfeio_config', None)

        def get_pdf_url(invoice_id, is_test_invoice, nfeio_config_name):
            pdf_result = nfeio.get_product_invoice_pdf(
                invoice_id, 
                force=True, 
                is_test_invoice=is_test_invoice,
                nfeio_config_name=nfeio_config_name
            )
            if pdf_result.get("success"):
                return pdf_result.get("pdf_url")
            return None

        def get_xml_url(invoice_id, is_test_invoice, nfeio_config_name):
            xml_result = nfeio.get_product_invoice_xml(
                invoice_id, 
                is_test_invoice=is_test_invoice,
                nfeio_config_name=nfeio_config_name
            )
            if xml_result.get("success"):
                return xml_result.get("xml_url")
            return None

        # Loop over max 5 times with 3 seconds wait
        pdf_url = None
        retries = 5
        wait = 3
        print(f"   🔄 Starting PDF/XML retrieval loop (max {retries} retries)")
        for i in range(retries):
            print(f"   📥 Attempt {i+1}/{retries} to get PDF and XML")
            pdf_url = get_pdf_url(invoice_id, is_test_invoice, nfeio_config_name)
            xml_url = get_xml_url(invoice_id, is_test_invoice, nfeio_config_name)
            print(f"      PDF URL: {'✓' if pdf_url else '✗'}")
            print(f"      XML URL: {'✓' if xml_url else '✗'}")
            if pdf_url and xml_url:
                break
            if i < retries - 1:  # Don't sleep on last iteration
                print(f"      ⏳ Waiting {wait}s before retry...")
                frappe.sleep(wait)

        if not pdf_url:
            print(f"   ⚠️ Failed to retrieve PDF URL after {retries} attempts")
            frappe.logger().error(
                "Failed to retrieve PDF URL for NFe.io ID: {}".format(invoice_id)
            )
        if not xml_url:
            print(f"   ⚠️ Failed to retrieve XML URL after {retries} attempts") 
            frappe.logger().error(
                "Failed to retrieve XML URL for NFe.io ID: {}".format(invoice_id)
            )

        # Get full invoice data to extract access key, number, serie
        # is_test_invoice and nfeio_config_name already retrieved above
        invoice_data_result = nfeio.get_product_invoice_by_id(
            invoice_id, 
            is_test_invoice=is_test_invoice,
            nfeio_config_name=nfeio_config_name
        )
        if invoice_data_result.get("success"):
            invoice_data = invoice_data_result.get("data", {})
            invoice_doc.invoice_access_key = invoice_data.get("authorization", {}).get(
                "accessKey"
            )
            invoice_doc.invoice_number = invoice_data.get("number")
            invoice_doc.invoice_serie = invoice_data.get("serie")

        invoice_doc.invoice_pdf_url = pdf_url
        invoice_doc.invoice_xml_url = xml_url
        invoice_doc.invoice_status = "Issued"
        invoice_doc.flags.ignore_processing_lock = True

        process_events = _get_events_from_invoice(invoice_doc, is_test_invoice, nfeio_config_name)
        invoice_doc.process_events = _make_json_prettier(process_events)

        invoice_doc.save(ignore_permissions=True)
        frappe.db.commit()

        print(f"   ✅ Successfully updated invoice {invoice_doc.name} to Issued status")
        print(f"      - Access Key: {invoice_doc.invoice_access_key}")
        print(f"      - Number: {invoice_doc.invoice_number}")
        print(f"      - Serie: {invoice_doc.invoice_serie}")
        print(f"      - PDF URL: {invoice_doc.invoice_pdf_url}")

        frappe.logger().info(
            "Updated Product Invoice {} with PDF and XML URLs.".format(invoice_doc.name)
        )

    except Exception as e:
        print(f"   ❌ Exception in handle_invoice_issued_status: {str(e)}")
        print(f"   📍 Traceback: {frappe.get_traceback()}")
        frappe.log_error(
            f"Error processing invoice issued webhook for NFe.io ID {invoice_id}: {str(e)}\n{frappe.get_traceback()}",
            "Invoice Issued Webhook Error",
        )


@frappe.whitelist()
def handle_invoice_error_status(data):
    """
    Handle webhook calls from NFe.io for invoice error status.
    """
    try:
        invoice_id = data.get("id")
        invoice_doc = frappe.get_doc("Product Invoice", {"invoice_id": invoice_id})

        if not invoice_doc:
            frappe.logger().error(
                "No Product Invoice found for NFe.io ID: {}".format(invoice_id)
            )
            return

        if _not_in_processing_status(invoice_doc):
            return

        error_message = data.get("error_message", "Unknown error")
        
        # Get is_test_invoice and nfeio_config from the document
        is_test_invoice = getattr(invoice_doc, 'is_test_invoice', 0)
        nfeio_config_name = getattr(invoice_doc, 'nfeio_config', None)

        invoice_doc.invoice_status = "Error"
        process_events = _get_events_from_invoice(invoice_doc, is_test_invoice, nfeio_config_name)
        invoice_doc.process_events = _make_json_prettier(process_events)

        invoice_doc.status_reason = (
            _get_error_from_events(invoice_doc, process_events, nfeio_config_name)
            or f"Could not retrieve error message. Defaulting to: {error_message}"
        )

        invoice_doc.flags.ignore_processing_lock = True
        invoice_doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(
            "Updated Product Invoice {} with Error status.".format(invoice_doc.name)
        )

    except Exception as e:
        frappe.log_error(
            f"Error processing invoice error webhook for NFe.io ID {invoice_id}: {str(e)}\n{frappe.get_traceback()}",
            "Invoice Error Webhook Error",
        )
