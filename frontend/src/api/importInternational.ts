import client from './client';

export interface InternationalImportConfig {
  usd_brl_rate: number;
  create_new_instruments: boolean;
  import_unit_price: boolean;
  import_quantities: boolean;
  period_date: string; // "YYYY-MM-DD"
}

export interface InternationalDiffItem {
  descricao: string;
  symbol: string | null;
  cusip: string | null;
  asset_class: 'UST' | 'CORP_BOND' | 'ETF';
  type: string;
  issuer: string;
  maturity_date: string | null;
  coupon_rate: number | null;
  quantidade: number;
  preco_usd: number;
  posicao_usd: number;
  posicao_brl: number;
  posicao_anterior_usd: number;
  variacion_usd: number;
  variacion_pct: number | null;
  match_status: 'EXACT' | 'MAPPED' | 'NEW';
  instrument_id: number | null;
  instrument_name_bd: string | null;
  balance_usd_bd: number | null;
  diff_status: 'NEW' | 'UPDATED' | 'UNCHANGED' | 'DISAPPEARED';
  will_create_instrument: boolean;
  warnings: string[];
}

export interface DividendDiffItem {
  pay_date: string;
  symbol: string | null;
  cusip: string | null;
  dividend_per_share: number;
  shares: number;
  valor_liquido_usd: number;
  valor_liquido_brl: number;
  withholding_rate: number;
  match_status: 'EXACT' | 'MAPPED' | 'NEW';
  instrument_id: number | null;
  instrument_name_bd: string | null;
  dup_status: 'NEW' | 'DUPLICATE';
}

export interface PreviewResponse {
  file_token: string;
  period_date: string;
  period_end: string | null;
  account_number: string | null;
  usd_brl_rate_suggested: number | null;
  positions_summary: {
    total_in_pdf: number;
    total_usd: number;
    total_brl: number;
    new_instruments: number;
    updated: number;
    unchanged: number;
    new: number;
  };
  dividends_summary: {
    total_in_pdf: number;
    total_usd_neto: number;
    total_brl_neto: number;
    new: number;
    duplicates: number;
  };
  position_diffs: InternationalDiffItem[];
  dividend_diffs: DividendDiffItem[];
  parse_warnings: string[];
}

export interface ManualMapping {
  key: string;
  instrument_id: number;
}

export interface ConfirmRequest {
  file_token: string;
  config: InternationalImportConfig;
  skip_cusips: string[];
  skip_dividend_indices: number[];
  manual_mappings: ManualMapping[];
}

export interface ConfirmResponse {
  success: boolean;
  positions_imported: {
    new_instruments: number;
    new_positions: number;
    updated_positions: number;
    skipped: number;
  };
  dividends_imported: {
    created: number;
    skipped_duplicates: number;
    skipped_manual: number;
  };
  warnings: string[];
}

export const previewInternational = async (
  file: File,
  periodDate: string,
  config: InternationalImportConfig,
): Promise<PreviewResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('period_date', periodDate);
  formData.append('config', JSON.stringify(config));
  const res = await client.post('/api/import/international/preview', formData, {
    timeout: 60000,
  });
  return res.data;
};

export const confirmInternational = async (
  payload: ConfirmRequest,
): Promise<ConfirmResponse> => {
  const res = await client.post('/api/import/international/confirm', payload);
  return res.data;
};

export const getUsdRateForMonth = async (month: string): Promise<{ rate: number; ref_date: string }> => {
  const res = await client.get(`/api/import/international/usd-rate?month=${month}`);
  return res.data;
};

export const mapInternationalInstrument = async (
  key: string,
  instrumentId: number,
): Promise<{ ok: boolean }> => {
  const res = await client.post('/api/import/international/map-instrument', {
    key,
    instrument_id: instrumentId,
  });
  return res.data;
};
