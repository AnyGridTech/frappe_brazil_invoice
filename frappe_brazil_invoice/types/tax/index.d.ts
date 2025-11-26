import { FrappeDoc } from "@anygridtech/frappe-types/client/frappe/core";

export interface TaxDoc extends FrappeDoc {
  // ICMS Tab
  // ICMS Próprio Section
  origin_icms?: string;
  mod_determ_bc?: string;
  base_calc_icms_fcp?: number;
  icms_value_fcp?: number;
  cst_icms?: string;
  base_calc_icms?: number;
  aliq_icms?: number;
  aliq_fcp?: number;
  calcular_automaticamente_icms?: number;
  adiciona_outras_despesas_icms?: number;
  adiciona_frete_icms?: number;
  adiciona_ipi_icms?: number;
  adiciona_seguro_icms?: number;
  aplicar_aliq_auto_icms?: number;

  // Substituição Tributária Section
  mod_base_calc_icms_trib?: string;
  cest_icms_trib?: string;
  base_icms_trib?: number;
  mva_trib?: number;
  credito_trib?: number;
  reducao_trib?: number;
  adiciona_outras_despesas_trib?: number;
  adiciona_frete_trib?: number;
  adiciona_ipi_trib?: number;
  adiciona_seguro_trib?: number;

  // Partilha ICMS Section
  valor_da_base_de_calculo_icms_no_destino?: number;
  aliq_do_icms_do_estado_de_destino?: number;
  aliq_do_icms_interestadual?: number;
  valor_da_base_de_calculo_fcp_na_uf_destino?: number;
  valor_icms_inter_puf_de_destino_difal?: number;
  aliq_fundo_pobre?: number;

  // IPI Tab
  cst_ipi?: string;
  base_de_calculo_ipi?: number;
  valor_do_ipi?: number;
  cod_enquadramento?: number;
  aliquota_ipi?: number;
  calcular_automaticamente_ipi?: number;

  // COFINS Tab
  cst_cofins?: string;
  base_de_calculo_cofins?: number;
  valor_cofins?: number;
  aliquota_cofins?: number;
  calcular_automaticamente_cofins?: number;

  // PIS Tab
  cst_pis?: string;
  base_de_calculo_pis?: number;
  valor_pis?: number;
  aliquota_pis?: number;
  calcular_automaticamente_pis?: number;

  // Internal Tab
  amended_from?: string;
}
