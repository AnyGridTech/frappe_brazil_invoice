import { InvoiceItem, InvoicesDoc, InvoiceTaxesDoc } from "../../../../types/invoice";
import { FrappeForm } from "@anygridtech/frappe-types/client/frappe/core";

/**
 * Calculate simple taxes based on value and tax percentage
 */
export function calcSimpleTaxes(value: number, tax: number): number {
  return (value * tax) / 100;
}

/**
 * Calculate all taxes for an invoice item
 */
export async function calculateItemTaxes(
  taxName: string,
  invoiceItem: InvoiceItem
): Promise<{ ipi: number; icms: number; pis: number; cofins: number } | undefined> {
  let doc: InvoiceTaxesDoc | undefined;

  await frappe.call({
    method: "frappe.client.get",
    args: {
      doctype: "Invoice Taxes",
      name: taxName,
    },
    callback: function (response) {
      if (!response || !response.message) {
        console.error("Failed to retrieve invoice tax document");
      } else {
        doc = response.message as InvoiceTaxesDoc;
      }
    },
  });

  if (!doc) {
    console.error("Failed to retrieve invoice tax document");
    return;
  }

  let ipi = calcSimpleTaxes(invoiceItem.rate, doc?.aliquota_ipi ?? 0);
  let icms = calcSimpleTaxes(invoiceItem.rate, doc?.aliq_icms ?? 0);

  // Add IPI to ICMS calculation if configured
  if (doc.adiciona_ipi_icms == 1) {
    icms += calcSimpleTaxes(invoiceItem.rate, doc?.aliquota_ipi ?? 0);
  }

  let pis = calcSimpleTaxes(invoiceItem.rate, doc?.aliquota_pis ?? 0);
  let cofins = calcSimpleTaxes(invoiceItem.rate, doc?.aliquota_cofins ?? 0);

  console.log("Aliquotas: Ipi: %d, Icms: %d, Pis: %d, Cofins: %d", ipi, icms, pis, cofins);
  console.log({ ipi, icms, pis, cofins });

  return { ipi, icms, pis, cofins };
}

/**
 * Sum total of all items in the invoice
 */
export function sumTotalItems(frm: FrappeForm<InvoicesDoc>) {
  const totalRate = frm.doc.items.reduce(function (sum: number, item: InvoiceItem) {
    return sum + (item.rate * item.quantity || 0);
  }, 0);

  const totalRateWithTaxes = frm.doc.items.reduce(function (sum: number, item: InvoiceItem) {
    return sum + (item.rate_taxes * item.quantity || 0);
  }, 0);

  frm.set_value("total", totalRate);
  frm.set_value("total_impostos", totalRateWithTaxes);
}

/**
 * Handle invoice_taxes field change for an item
 */
export async function handleInvoiceTaxesChange(
  frm: FrappeForm<InvoicesDoc>,
  cdt: string,
  cdn: string
) {
  const row = frappe.get_doc<InvoiceItem>(cdt, cdn);
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

  frm.refresh_field("items");
  sumTotalItems(frm);
}

// Uncomment if needed for future use
// /**
//  * Calculate DIFAL (Diferencial de Alíquota)
//  */
// function difalCalc(
//   baseCalc: number,
//   aliquotaInternal: number,
//   aliquotaInterState: number,
//   icmsOrig: number
// ): number {
//   const icmsIntState = aliquotaInterState / 100; // icms do estado de origem
//   const icmsInternal = aliquotaInternal / 100; // icms do estado de destino
//   const difal =
//     ((baseCalc - icmsOrig) / (1 - icmsInternal)) * icmsInternal - baseCalc * icmsIntState;
//   return difal;
// }
