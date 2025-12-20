// Copyright (c) 2025, AnyGridTech and contributors
// For license information, please see license.txt
"use strict";
(() => {
  // brazil_invoice/doctype/invoices/ts/cep.ts
  function formatCEP(cep) {
    const cleaned = cep.replace(/\D/g, "");
    if (cleaned.length === 8) {
      return `${cleaned.slice(0, 5)}-${cleaned.slice(5)}`;
    }
    return cep;
  }
  async function fetchAddressFromCEP(cep) {
    try {
      const cleanedCEP = cep.replace(/\D/g, "");
      if (cleanedCEP.length !== 8) {
        return null;
      }
      const response = await fetch(`https://viacep.com.br/ws/${cleanedCEP}/json/`);
      if (!response.ok) {
        throw new Error("Failed to fetch CEP data");
      }
      const data = await response.json();
      if (data.erro) {
        frappe.msgprint({
          title: __("CEP Not Found"),
          indicator: "orange",
          message: __("The provided CEP was not found in the database")
        });
        return null;
      }
      return data;
    } catch (error) {
      console.error("Error fetching CEP:", error);
      frappe.msgprint({
        title: __("Error"),
        indicator: "red",
        message: __("Failed to fetch address data. Please check your internet connection.")
      });
      return null;
    }
  }
  async function processCEPLookup(frm) {
    if (!frm.doc.delivery_cep) return;
    const cleanedCEP = frm.doc.delivery_cep.replace(/\D/g, "");
    if (cleanedCEP.length !== 8) return;
    const formattedCEP = formatCEP(frm.doc.delivery_cep);
    if (frm.doc.delivery_cep !== formattedCEP) {
      frm.doc.delivery_cep = formattedCEP;
      frm.refresh_field("delivery_cep");
    }
    const addressData = await fetchAddressFromCEP(formattedCEP);
    if (addressData) {
      frm.doc.delivery_address = addressData.logradouro || "";
      frm.doc.delivery_neighborhood = addressData.bairro || "";
      frm.doc.city = addressData.localidade || "";
      frm.doc.delivery_state = addressData.uf || "";
      frm.doc.delivery_ibge = addressData.ibge || "";
      frm.refresh_field("delivery_address");
      frm.refresh_field("delivery_neighborhood");
      frm.refresh_field("city");
      frm.refresh_field("delivery_state");
      frm.refresh_field("delivery_ibge");
      frappe.show_alert({
        message: __("Address filled successfully"),
        indicator: "green"
      }, 3);
    }
  }
  function setupCEPField(frm) {
    frm.set_query("delivery_state", function() {
      return {
        filters: {
          country: "Brazil"
        }
      };
    });
    const cepField = frm.fields_dict["delivery_cep"];
    if (cepField && cepField.$input) {
      cepField.$input.on("keypress", function(e) {
        if (e.keyCode === 8 || e.keyCode === 9 || e.keyCode === 27 || e.keyCode === 13 || e.keyCode === 46 || // Allow: Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X
        e.keyCode === 65 && e.ctrlKey === true || e.keyCode === 67 && e.ctrlKey === true || e.keyCode === 86 && e.ctrlKey === true || e.keyCode === 88 && e.ctrlKey === true) {
          return;
        }
        if (e.which < 48 || e.which > 57) {
          e.preventDefault();
        }
      });
      cepField.$input.on("paste", function() {
        setTimeout(function() {
          if (cepField.$input) {
            const pastedValue = cepField.$input.val();
            const cleanedValue = pastedValue.replace(/\D/g, "");
            cepField.$input.val(cleanedValue);
            frm.doc.delivery_cep = cleanedValue;
            frm.refresh_field("delivery_cep");
          }
        }, 10);
      });
      cepField.$input.on("input", function() {
        const cleanedCEP = frm.doc.delivery_cep ? frm.doc.delivery_cep.replace(/\D/g, "") : "";
        if (cleanedCEP.length === 8) {
          processCEPLookup(frm);
        }
      });
    }
  }

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
    onload: function(frm) {
      setupCEPField(frm);
    },
    refresh: function(frm) {
      if (frm.doc.docstatus === 1 && !frm.doc.invoice_id) {
        frm.add_custom_button(__("Create NFe Invoice"), function() {
          frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.invoices.invoices.process_invoice",
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
        }, __("Actions"));
      }
      if (frm.doc.invoice_id) {
        frm.add_custom_button(__("Check NFe Status"), function() {
          frappe.call({
            method: "frappe_brazil_invoice.brazil_invoice.doctype.invoices.invoices.get_invoice_status",
            args: {
              invoice_name: frm.doc.name
            },
            callback: function(r) {
              if (r.message && r.message.success) {
                const data = r.message.data;
                frappe.msgprint({
                  title: __("Invoice Status"),
                  indicator: "blue",
                  message: `
                  <p><strong>ID:</strong> ${data.id || "N/A"}</p>
                  <p><strong>Status:</strong> ${data.status || "N/A"}</p>
                  <p><strong>Environment:</strong> ${data.environment || "N/A"}</p>
                  <p><strong>Flow Status:</strong> ${data.flowStatus || "N/A"}</p>
                `
                });
              } else {
                frappe.msgprint({
                  title: __("Error"),
                  indicator: "red",
                  message: r.message.message || __("Failed to get invoice status")
                });
              }
            }
          });
        }, __("Actions"));
        if (frm.doc.invoice_link) {
          frm.add_custom_button(__("View NFe PDF"), function() {
            window.open(frm.doc.invoice_link, "_blank");
          }, __("Actions"));
        }
      }
    },
    tax_template: async function(frm) {
      await applyTaxTemplateToItems(frm);
    },
    delivery_cep: async function(frm) {
      await processCEPLookup(frm);
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
