import { InvoicesDoc } from "../../../../types/invoice";
import { FrappeForm } from "@anygridtech/frappe-types/client/frappe/core";

/**
 * Format CEP to standard format (xxxxx-xxx)
 */
export function formatCEP(cep: string): string {
  const cleaned = cep.replace(/\D/g, "");
  if (cleaned.length === 8) {
    return `${cleaned.slice(0, 5)}-${cleaned.slice(5)}`;
  }
  return cep;
}

/**
 * Fetch address data from ViaCEP API
 */
export async function fetchAddressFromCEP(cep: string): Promise<{
  logradouro: string;
  bairro: string;
  localidade: string;
  uf: string;
  ibge: string;
  erro?: boolean;
} | null> {
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
        message: __("The provided CEP was not found in the database"),
      });
      return null;
    }

    return data;
  } catch (error) {
    console.error("Error fetching CEP:", error);
    frappe.msgprint({
      title: __("Error"),
      indicator: "red",
      message: __("Failed to fetch address data. Please check your internet connection."),
    });
    return null;
  }
}

/**
 * Process CEP and fill address fields
 */
export async function processCEPLookup(frm: FrappeForm<InvoicesDoc>) {
  if (!frm.doc.delivery_cep) return;

  const cleanedCEP = frm.doc.delivery_cep.replace(/\D/g, "");
  
  // Only proceed if we have exactly 8 digits
  if (cleanedCEP.length !== 8) return;

  // Format the CEP field
  const formattedCEP = formatCEP(frm.doc.delivery_cep);
  if (frm.doc.delivery_cep !== formattedCEP) {
    frm.doc.delivery_cep = formattedCEP;
    frm.refresh_field("delivery_cep");
  }

  // Fetch and auto-fill address fields based on CEP
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
      indicator: "green",
    }, 3);
  }
}

/**
 * Setup CEP field with validation and auto-complete functionality
 */
export function setupCEPField(frm: FrappeForm<InvoicesDoc>) {
  // Set up state filter
  frm.set_query("delivery_state", function () {
    return {
      filters: {
        country: "Brazil",
      },
    };
  });

  // Add input event listener for real-time checking when 8 digits are entered
  const cepField = frm.fields_dict["delivery_cep"];
  if (cepField && cepField.$input) {
    // Restrict input to numbers only
    cepField.$input.on("keypress", function (e: JQuery.KeyPressEvent) {
      // Allow: backspace, delete, tab, escape, enter
      if (
        e.keyCode === 8 ||
        e.keyCode === 9 ||
        e.keyCode === 27 ||
        e.keyCode === 13 ||
        e.keyCode === 46 ||
        // Allow: Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X
        (e.keyCode === 65 && e.ctrlKey === true) ||
        (e.keyCode === 67 && e.ctrlKey === true) ||
        (e.keyCode === 86 && e.ctrlKey === true) ||
        (e.keyCode === 88 && e.ctrlKey === true)
      ) {
        return;
      }
      
      // Ensure that it is a number and stop the keypress if not
      if ((e.which < 48 || e.which > 57)) {
        e.preventDefault();
      }
    });

    // Handle paste event to remove non-numeric characters
    cepField.$input.on("paste", function () {
      setTimeout(function () {
        if (cepField.$input) {
          const pastedValue = cepField.$input.val() as string;
          const cleanedValue = pastedValue.replace(/\D/g, "");
          cepField.$input.val(cleanedValue);
          frm.doc.delivery_cep = cleanedValue;
          frm.refresh_field("delivery_cep");
        }
      }, 10);
    });

    cepField.$input.on("input", function () {
      const cleanedCEP = frm.doc.delivery_cep ? frm.doc.delivery_cep.replace(/\D/g, "") : "";
      
      // Trigger lookup when exactly 8 digits are entered
      if (cleanedCEP.length === 8) {
        processCEPLookup(frm);
      }
    });
  }
}
