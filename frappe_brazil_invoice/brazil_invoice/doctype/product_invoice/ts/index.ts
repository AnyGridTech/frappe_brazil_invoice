import { Inverter, InvoiceItem, InvoicesDoc } from "../../../../types/invoice";
import { handleInvoiceTaxesChange, sumTotalItems, applyTaxTemplateToItems } from "./tax";
import { setupCEPField, processCEPLookup } from "./cep";

frappe.ui.form.on<InvoicesDoc>("Product Invoice", "before_save", async (form) => {
  var clientType = form.doc.client_type;
  if (clientType === "PF") {
    if (!cpfValid(form.doc.client_id_number || "")) {
      frappe.msgprint("CPF Inválido");
      frappe.validated = false;
    }
  }
  if (clientType === "PJ") {
    if (!form.doc.client_id_number || form.doc.client_id_number.length != 14) {
      frappe.msgprint("CNPJ Inválido");
      frappe.validated = false;
    }
  }
});

frappe.ui.form.on<InvoicesDoc>("Product Invoice", {
  onload: function (frm) {
    setupCEPField(frm);
  },
  
  refresh: function(frm) {
    // Add "Create NFe Invoice" button
    if (frm.doc.docstatus === 1 && !frm.doc.invoice_id) {
      // Only show button if document is submitted and invoice not yet created
      frm.add_custom_button(__('Create NFe Invoice'), function() {
        frappe.call({
          method: 'frappe_brazil_invoice.brazil_invoice.doctype.invoices.invoices.process_invoice',
          args: {
            invoice_name: frm.doc.name
          },
          freeze: true,
          callback: function(r) {
            if (r.message && r.message.success) {
              frm.reload_doc();
            }
          }
        });
      }, __('Actions'));
    }
    
    // Add "Check Status" button if invoice was already created
    if (frm.doc.invoice_id) {
      frm.add_custom_button(__('Check NFe Status'), function() {
        frappe.call({
          method: 'frappe_brazil_invoice.brazil_invoice.doctype.invoices.invoices.get_invoice_status',
          args: {
            invoice_name: frm.doc.name
          },
          callback: function(r) {
            if (r.message && r.message.success) {
              const data = r.message.data;
              frappe.msgprint({
                title: __('Invoice Status'),
                indicator: 'blue',
                message: `
                  <p><strong>ID:</strong> ${data.id || 'N/A'}</p>
                  <p><strong>Status:</strong> ${data.status || 'N/A'}</p>
                  <p><strong>Environment:</strong> ${data.environment || 'N/A'}</p>
                  <p><strong>Flow Status:</strong> ${data.flowStatus || 'N/A'}</p>
                `
              });
            } else {
              frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: r.message.message || __('Failed to get invoice status')
              });
            }
          }
        });
      }, __('Actions'));
      
      // Add "View PDF" button
      if (frm.doc.invoice_pdf_url) {
        frm.add_custom_button(__('View NFe PDF'), function() {
          window.open(frm.doc.invoice_pdf_url, '_blank');
        }, __('Actions'));
      }
      
      // Add "View XML" button
      if (frm.doc.invoice_xml_url) {
        frm.add_custom_button(__('View NFe XML'), function() {
          window.open(frm.doc.invoice_xml_url, '_blank');
        }, __('Actions'));
      }
    }
  },
  
  tax_template: async function (frm) {
    await applyTaxTemplateToItems(frm);
  },
  
  delivery_cep: async function (frm) {
    await processCEPLookup(frm);
  },
});

frappe.ui.form.on<InvoicesDoc>("Item Invoice", {
  refresh: function (frm) {
    // Refresh logic here if needed
    sumTotalItems(frm);
  },

  
  serial_number: function (frm, cdt, cdn) {
    // Handle serial_no field change
    console.log("Serial number changed event triggered");
    let row = frappe.get_doc<InvoiceItem>(cdt as string, cdn);
    if (!row || !row.serial_number || row.serial_number.length < 1) {
      return
    }
    frappe.call({
      method: "frappe.client.get",
      args: {
        doctype: "Serial No",
        filters: {
          name: row.serial_number
        }
      },
      callback: function (response) {
        if (!response){
          console.error("Failed to retrieve serial number details");
          return
        }
        frappe.call({
          method: "frappe.client.get",
          args: {
            doctype: "Item",
            filters: {
              name: response.message.item_code
            }
          },
          callback: function (response) {
            if (!response) {
              console.error("Failed to retrieve serial number details");
              return;
            }
            const item = response.message as Inverter;
            row.item_code = item.item_code;
            row.item_name = item.item_name;
            row.quantity = row.quantity ?? 1;
            row.rate = item.valuation_rate ?? 0;
            row.rate_taxes = item.valuation_rate ?? 0;
            row.ncm = item.ncm;
            row.description = item.description || "";
            frm.refresh_field("invoices_table");
            sumTotalItems(frm);
          }
        });
      }
    });
    
    console.log("Serial number changed:", row.serial_number);
  },
  invoice_taxes: async function (frm, cdt, cdn) {
    if (!cdt || !cdn) return;
    await handleInvoiceTaxesChange(frm, cdt, cdn);
  },
  amount: function (frm, cdt, cdn) {
    const row = frappe.get_doc<InvoiceItem>(cdt as string, cdn);
    if (!row) {
      return;
    }
    frm.refresh_field("invoices_table");
    sumTotalItems(frm);
  },
  
});

function cpfValid(strCPF: string): boolean {
  var Soma;
  var Resto;
  Soma = 0;
  var i;
  if (strCPF == "00000000000") return false;

  for (i = 1; i <= 9; i++) Soma = Soma + parseInt(strCPF.substring(i - 1, i)) * (11 - i);
  Resto = (Soma * 10) % 11;

  if (Resto == 10 || Resto == 11) Resto = 0;
  if (Resto != parseInt(strCPF.substring(9, 10))) return false;

  Soma = 0;
  for (i = 1; i <= 10; i++) Soma = Soma + parseInt(strCPF.substring(i - 1, i)) * (12 - i);
  Resto = (Soma * 10) % 11;

  if (Resto == 10 || Resto == 11) Resto = 0;
  if (Resto != parseInt(strCPF.substring(10, 11))) return false;
  return true;
}