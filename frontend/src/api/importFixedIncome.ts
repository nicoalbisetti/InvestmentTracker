import client from './client';

export interface ImportConfig {
  import_values: boolean;
  import_value_curva: boolean;
  import_value_mtm: boolean;
  value_change_threshold_pct: number | null;
  import_quantities: boolean;
  alert_quantity_change: boolean;
  import_instrument_data: boolean;
  import_maturity_date: boolean;
  import_issue_date: boolean;
  import_indexador: boolean;
  import_custodian: boolean;
  import_name: boolean;
  create_new_instruments: boolean;
  create_base_only: boolean;
  import_unit_price: boolean;
  custodian_filter: string | null;
}

export interface DiffItem {
  status: 'NEW' | 'UPDATED' | 'UNCHANGED' | 'DISAPPEARED';
  codigo: string;
  nome: string;
  tipo: string;
  emissor: string;
  custodian: string;
  custodian_override: string | null;
  indexador: string | null;
  emissao: string | null;
  vencimento: string | null;
  in_liquidation: boolean;
  valor_actual_brl: number | null;
  valor_anterior_brl: number | null;
  variacion_brl: number | null;
  variacion_pct: number | null;
  cantidad_actual: number | null;
  cantidad_anterior: number | null;
  unit_price: number | null;
  capital_invested: number | null;
  ultimo_valor_brl: number | null;
  ultima_fecha: string | null;
  instrument_id: number | null;
  warnings: string[];
}

export interface PreviewResponse {
  file_token: string;
  period_date: string;
  summary: {
    total_in_file: number;
    new_instruments: number;
    updated_positions: number;
    unchanged: number;
    disappeared: number;
    parse_errors: number;
    no_price_available: number;
  };
  differences: DiffItem[];
  parse_warnings: string[];
  expires_at: string;
}

export interface ImportResult {
  success: boolean;
  imported: {
    new_instruments: number;
    new_positions: number;
    updated_positions: number;
    closed_instruments?: number;
  };
  skipped: number;
  warnings: string[];
  errors: string[];
}

export function itemKey(item: DiffItem): string {
  return `${item.codigo}::${item.custodian_override ?? ''}`;
}

export const previewImport = async (
  file: File,
  periodDate: string,
  config: ImportConfig,
): Promise<PreviewResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('period_date', periodDate);
  formData.append('config', JSON.stringify(config));
  const res = await client.post('/api/import/fixed-income/preview', formData);
  return res.data;
};

export const confirmImport = async (
  fileToken: string,
  periodDate: string,
  config: ImportConfig,
  skipKeys: string[],
): Promise<ImportResult> => {
  const res = await client.post('/api/import/fixed-income/confirm', {
    file_token: fileToken,
    period_date: periodDate,
    config,
    skip_codes: skipKeys,
  });
  return res.data;
};

export const mapInstrument = async (
  codigoExcel: string,
  instrumentId: number,
  fileToken?: string,
  custodianOverride?: string | null,
): Promise<{ ok: boolean; instrument_name: string }> => {
  const res = await client.post('/api/import/fixed-income/map-instrument', {
    codigo_excel: codigoExcel,
    instrument_id: instrumentId,
    file_token: fileToken,
    custodian_override: custodianOverride ?? null,
  });
  return res.data;
};

export interface SuggestionItem {
  id: number;
  name: string;
  custodian: string;
  maturity_date: string | null;
  score: number;
}

export const getSuggestions = async (fileToken: string, codigo: string): Promise<SuggestionItem[]> => {
  const res = await client.get('/api/import/fixed-income/suggestions', {
    params: { file_token: fileToken, codigo },
  });
  return res.data.suggestions;
};

export const getLastFixedIncomeDate = (): Promise<{ date: string | null }> =>
  client.get('/api/positions/last-fixed-income-date').then(r => r.data);
