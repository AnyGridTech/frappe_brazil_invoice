import { FrappeDoc } from "@anygridtech/frappe-types/client/frappe/core";
import { Item } from "@anygridtech/frappe-types/doctype/erpnext/Item";

export interface InvoicesDoc extends FrappeDoc {
  operation_nature?: string;
  carrier?: string;
  modalidade_de_frete?: string;
  client_type?: string;
  contribuinte_icms?: string;
  state_tax_number?: string;
  tax_template?: string;
  nf_de_retorno?: string;
  nf_ref_serie?: string;
  nf_ref_numero?: string;
  nf_chave_de_acesso?: string;
  nome?: string;
  email?: string;
  telefone?: string;
  client_id_number?: string; // CPF/CNPJ
  items_section?: string;
  invoices_table: InvoiceItem[];
  scan_barcode?: string;
  invoice_id?: string;
  invoice_link?: string;
  total?: string;
  total_impostos?: string;
  collectguy?: string;
  cep?: string;
  address?: string;
  neighborhood?: string;
  ibge?: string;
  deliveryphone?: string;
  state?: string;
  city?: string;
  number_address?: string;
  complement?: string;
  small_text_cyhn?: string;
  errors_field?: string;
  internal_tab?: string;
  amended_from?: string;
}
export interface Inverter extends Item {
  ncm: string;
  package_length: number;
  package_width: number;
  package_height: number;
  weight_per_unit: number;
}
export interface InvoiceItem extends FrappeDoc {
  // Details Section
  serial_number?: string;
  item_code?: string;
  item_name?: string;
  rate: number;
  quantity: number;
  ncm?: string;
  // Tax Section
  invoice_taxes: string;
  icms_rate: number;
  ipi_rate: number;
  rate_taxes: number;
  pis_rate: number;
  cofins_rate: number;
  // Additional fields not in JSON but used in code
  description: string;
}