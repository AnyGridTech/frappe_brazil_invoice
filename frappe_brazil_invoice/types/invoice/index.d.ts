import { FrappeDoc } from "@anygridtech/frappe-types/client/frappe/core";
import { Item } from "@anygridtech/frappe-types/doctype/erpnext/Item";

export interface InvoicesDoc extends FrappeDoc {
  // Section Break XRUR
  operation_type?: string; // Natureza de Operação
  client_type?: string; // Tipo de Cliente (PF/PJ)
  freight_modality?: string; // Modalidade de Frete
  nf_ref_serie?: string; // NF Ref. Série
  nf_ref_num?: string; // NF Ref. Número
  nf_ref_access_key?: string; // NF Ref. Chave de Acesso
  nf_de_retorno?: number; // NF de Retorno? (Check)

  // Section Break GOAB - Client Info
  client_name?: string; // Nome / Razão Social
  client_email?: string; // Email
  contribuinte_icms?: string; // Contribuinte ICMS
  client_phone?: string; // Telefone de Contato
  client_id_number?: string; // CPF / CNPJ
  inscricao_estadual?: string; // Inscrição Estadual (IE)

  // Produto Section
  tax_template?: string; // Tax Template
  invoices_table: InvoiceItem[]; // Table of items

  // Section Break JXVL - Transport Info
  product_brand?: string; // Marca
  product_quantity?: string; // Quantidade
  product_type?: string; // Espécie
  carrier?: string; // Transportadora
  product_gross_weight?: string; // Peso Bruto
  product_net_weight?: string; // Peso Líquido

  // Dados Adicionais Section
  additional_information?: string; // Informações Complementares

  // Totais Section
  total_freight?: string; // Frete
  total_discount?: string; // Desconto
  total_insurance?: string; // Seguro
  other_expenses?: string; // Outras Despesas
  total?: string; // Total
  total_tax?: string; // Total + Impostos

  // Endereço Section - Delivery Address
  delivery_supervisor?: string; // Responsável
  delivery_cep?: string; // CEP
  delivery_address?: string; // Endereço
  delivery_neighborhood?: string; // Bairro
  delivery_ibge?: string; // IBGE
  delivery_phone?: string; // Telefone de Contato
  delivery_state?: string; // Estado
  city?: string; // Cidade
  delivery_number_address?: string; // Nº do Endereço
  delivery_complement?: string; // Complemento

  // Eventos Sefaz Section
  invoice_id?: string; // Invoice ID
  invoice_serie?: string; // Invoice Serie
  invoice_link?: string; // Invoice Link
  invoice_number?: string; // Invoice Number

  // Section Break FPDY
  process_events?: string; // Logs

  // Internal Tab
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