// Copyright (c) 2025, AnyGridTech and contributors
// For license information, please see license.txt
"use strict";
(() => {
  // brazil_invoice/doctype/invoices/ts/tax.ts
  function calcSimpleTaxes(value, tax) {
    return value * tax / 100;
  }
  async function calculateItemTaxes(taxName, invoiceItem) {
    let doc;
    await frappe.call({
      method: "frappe.client.get",
      args: {
        doctype: "Tax",
        name: taxName
      },
      callback: function(response) {
        if (!response || !response.message) {
          console.error("Failed to retrieve invoice tax document");
        } else {
          doc = response.message;
        }
      }
    });
    if (!doc) {
      console.error("Failed to retrieve invoice tax document");
      return;
    }
    let ipi = calcSimpleTaxes(invoiceItem.rate, doc?.aliquota_ipi ?? 0);
    let icms = calcSimpleTaxes(invoiceItem.rate, doc?.aliq_icms ?? 0);
    if (doc.adiciona_ipi_icms == 1) {
      icms += calcSimpleTaxes(invoiceItem.rate, doc?.aliquota_ipi ?? 0);
    }
    let pis = calcSimpleTaxes(invoiceItem.rate, doc?.aliquota_pis ?? 0);
    let cofins = calcSimpleTaxes(invoiceItem.rate, doc?.aliquota_cofins ?? 0);
    console.log("Aliquotas: Ipi: %d, Icms: %d, Pis: %d, Cofins: %d", ipi, icms, pis, cofins);
    console.log({ ipi, icms, pis, cofins });
    return { ipi, icms, pis, cofins };
  }
  function sumTotalItems(frm) {
    const totalRate = frm.doc.invoices_table.reduce(function(sum, item) {
      return sum + (item.rate || 0) * (item.quantity || 0);
    }, 0);
    const totalWithTax = frm.doc.invoices_table.reduce(function(sum, item) {
      const itemTotalWithTax = (item.rate_taxes || 0) * (item.quantity || 0);
      return sum + itemTotalWithTax;
    }, 0);
    frm.set_value("total", totalRate);
    frm.set_value("total_tax", totalWithTax);
  }
  async function applyTaxTemplateToItems(frm) {
    if (!frm.doc.tax_template || frm.doc.tax_template.length < 1) {
      console.log("No tax template selected");
      return;
    }
    if (!frm.doc.invoices_table || frm.doc.invoices_table.length < 1) {
      console.log("No invoices_table to apply tax template");
      return;
    }
    for (const item of frm.doc.invoices_table) {
      item.invoice_taxes = frm.doc.tax_template;
      const taxes = await calculateItemTaxes(item.invoice_taxes, item);
      if (!taxes) {
        console.error("Failed to calculate taxes for item:", item.name);
        continue;
      }
      item.ipi_rate = taxes.ipi;
      item.icms_rate = taxes.icms;
      item.pis_rate = taxes.pis;
      item.cofins_rate = taxes.cofins;
      item.rate_taxes = taxes.ipi + taxes.icms + taxes.pis + taxes.cofins + item.rate;
    }
    frm.refresh_field("invoices_table");
    sumTotalItems(frm);
  }
  async function handleInvoiceTaxesChange(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    if (!row) {
      return;
    }
    if (row.invoice_taxes.length < 1) {
      return;
    }
    const taxes = await calculateItemTaxes(row.invoice_taxes, row);
    console.log(row.invoice_taxes);
    if (!taxes) {
      console.error("Failed to calculate taxes");
      return;
    }
    row.ipi_rate = taxes.ipi;
    row.icms_rate = taxes.icms;
    row.pis_rate = taxes.pis;
    row.cofins_rate = taxes.cofins;
    row.rate_taxes = taxes.ipi + taxes.icms + taxes.pis + taxes.cofins + row.rate;
    frm.refresh_field("invoices_table");
    sumTotalItems(frm);
  }

  // brazil_invoice/doctype/invoices/ts/index.ts
  frappe.ui.form.on("Invoices", "before_save", async (form) => {
    var clientType = form.doc.client_type;
    if (clientType === "PF") {
      if (!cpfValid(form.doc.client_id_number || "")) {
        frappe.msgprint("CPF Inv\xE1lido");
        frappe.validated = false;
      }
    }
    if (clientType === "PJ") {
      if (!form.doc.client_id_number || form.doc.client_id_number.length != 14) {
        frappe.msgprint("CNPJ Inv\xE1lido");
        frappe.validated = false;
      }
    }
  });
  frappe.ui.form.on("Invoices", {
    tax_template: async function(frm) {
      await applyTaxTemplateToItems(frm);
    }
  });
  frappe.ui.form.on("Item Invoice", {
    refresh: function(frm) {
      sumTotalItems(frm);
    },
    serial_number: function(frm, cdt, cdn) {
      console.log("Serial number changed event triggered");
      let row = frappe.get_doc(cdt, cdn);
      if (!row || !row.serial_number || row.serial_number.length < 1) {
        return;
      }
      frappe.call({
        method: "frappe.client.get",
        args: {
          doctype: "Serial No",
          filters: {
            name: row.serial_number
          }
        },
        callback: function(response) {
          if (!response) {
            console.error("Failed to retrieve serial number details");
            return;
          }
          frappe.call({
            method: "frappe.client.get",
            args: {
              doctype: "Item",
              filters: {
                name: response.message.item_code
              }
            },
            callback: function(response2) {
              if (!response2) {
                console.error("Failed to retrieve serial number details");
                return;
              }
              const item = response2.message;
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
    invoice_taxes: async function(frm, cdt, cdn) {
      if (!cdt || !cdn) return;
      await handleInvoiceTaxesChange(frm, cdt, cdn);
    },
    amount: function(frm, cdt, cdn) {
      const row = frappe.get_doc(cdt, cdn);
      if (!row) {
        return;
      }
      frm.refresh_field("invoices_table");
      sumTotalItems(frm);
    }
  });
  function cpfValid(strCPF) {
    var Soma;
    var Resto;
    Soma = 0;
    var i;
    if (strCPF == "00000000000") return false;
    for (i = 1; i <= 9; i++) Soma = Soma + parseInt(strCPF.substring(i - 1, i)) * (11 - i);
    Resto = Soma * 10 % 11;
    if (Resto == 10 || Resto == 11) Resto = 0;
    if (Resto != parseInt(strCPF.substring(9, 10))) return false;
    Soma = 0;
    for (i = 1; i <= 10; i++) Soma = Soma + parseInt(strCPF.substring(i - 1, i)) * (12 - i);
    Resto = Soma * 10 % 11;
    if (Resto == 10 || Resto == 11) Resto = 0;
    if (Resto != parseInt(strCPF.substring(10, 11))) return false;
    return true;
  }
})();
