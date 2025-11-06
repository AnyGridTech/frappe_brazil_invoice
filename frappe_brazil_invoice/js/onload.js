frappe.ui.form.on("Invoice", "before_save", async (form) => {
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
frappe.ui.form.on("Invoice Item", {
    refresh: function (frm) {
        sumTotalItems(frm);
    },
    serial_no: function (frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        if (!row || row.serial_no.length < 1) {
            return;
        }
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Serial No",
                filters: {
                    name: row.serial_no
                }
            },
            callback: function (response) {
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
                    callback: function (response) {
                        if (!response) {
                            console.error("Failed to retrieve serial number details");
                            return;
                        }
                        const item = response.message;
                        row.item_code = item.item_code;
                        row.item_name = item.item_name;
                        row.amount = row.amount ?? 1;
                        row.rate = item.valuation_rate ?? 0;
                        row.rate_taxes = item.valuation_rate ?? 0;
                        frm.refresh_field("items");
                        sumTotalItems(frm);
                    }
                });
            }
        });
        console.log("Serial number changed:", row.serial_no);
    },
    invoice_taxes: async function (frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (!row) {
            return;
        }
        if (row.invoice_taxes.length < 1) {
            return;
        }
        const taxes = await taxescalc(row.invoice_taxes, row);
        console.log(row.invoice_taxes);
        if (!taxes) {
            console.error("Failed to calculate taxes");
            return;
        }
        row.rate_taxes = (taxes.ipi + taxes.icms + taxes.pis + taxes.cofins) + row.rate;
        frm.refresh_field("items");
        sumTotalItems(frm);
    },
    amount: function (frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (!row) {
            return;
        }
        frm.refresh_field("items");
        sumTotalItems(frm);
    },
});
function sumTotalItems(frm) {
    var total_rate = frm.doc.items.reduce(function (sum, item) {
        return sum + ((item.rate * item.amount) || 0);
    }, 0);
    var total_rate_with_taxes = frm.doc.items.reduce(function (sum, item) {
        return sum + ((item.rate_taxes * item.amount) || 0);
    }, 0);
    frm.set_value("total", total_rate);
    frm.set_value("total_impostos", total_rate_with_taxes);
}
async function taxescalc(name, InvoiceItem) {
    let doc;
    await frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Invoice Taxes",
            name: name
        },
        callback: function (response) {
            if (!response || !response.message) {
                console.error("Failed to retrieve invoice tax document");
            }
            else {
                doc = response.message;
            }
        }
    });
    if (!doc) {
        console.error("Failed to retrieve invoice tax document");
        return;
    }
    let ipi = calcSimpleTaxes(InvoiceItem.rate, doc?.aliquota_ipi ?? 0);
    let icms = calcSimpleTaxes(InvoiceItem.rate, doc?.aliq_icms ?? 0);
    if (doc.adiciona_ipi_icms == 1) {
        icms += calcSimpleTaxes(InvoiceItem.rate, doc?.aliquota_ipi ?? 0);
    }
    let pis = calcSimpleTaxes(InvoiceItem.rate, doc?.aliquota_pis ?? 0);
    let cofins = calcSimpleTaxes(InvoiceItem.rate, doc?.aliquota_cofins ?? 0);
    console.log("Aliquotas: Ipi: %d, Icms: %d, Pis: %d, Cofins: %d", ipi, icms, pis, cofins);
    console.log({ ipi, icms, pis, cofins });
    return { ipi, icms, pis, cofins };
}
function cpfValid(strCPF) {
    var Soma;
    var Resto;
    Soma = 0;
    var i;
    if (strCPF == "00000000000")
        return false;
    for (i = 1; i <= 9; i++)
        Soma = Soma + parseInt(strCPF.substring(i - 1, i)) * (11 - i);
    Resto = (Soma * 10) % 11;
    if ((Resto == 10) || (Resto == 11))
        Resto = 0;
    if (Resto != parseInt(strCPF.substring(9, 10)))
        return false;
    Soma = 0;
    for (i = 1; i <= 10; i++)
        Soma = Soma + parseInt(strCPF.substring(i - 1, i)) * (12 - i);
    Resto = (Soma * 10) % 11;
    if ((Resto == 10) || (Resto == 11))
        Resto = 0;
    if (Resto != parseInt(strCPF.substring(10, 11)))
        return false;
    return true;
}
function calcSimpleTaxes(value, tax) {
    return (value * tax) / 100;
}
