import client from './client';

export interface DiffItem {
  index: number;
  status: 'NEW' | 'DUPLICATE' | 'CONFLICT' | 'NO_MATCH' | 'AMBIGUOUS_MATCH';
  produto_raw: string;
  ticker: string | null;
  nombre_busqueda: string;
  tipo_evento_raw: string;
  custodian: string;
  fecha_pago: string;
  cantidad: number | null;
  precio_unitario: number | null;
  amount_brl: number;
  type: string;
  instrument_id: number | null;
  instrument_name: string | null;
  instrument_ticker: string | null;
  existing_amount_brl: number | null;
  match_candidates: { id: number; name: string; ticker: string | null }[];
  warnings: string[];
}

export interface PreviewSummary {
  total_in_file: number;
  total_amount_brl: number;
  total_validated: boolean;
  new: number;
  duplicates: number;
  conflicts: number;
  no_match: number;
  ambiguous_match: number;
}

export interface PreviewResponse {
  file_token: string;
  period_label: string;
  expires_at: string;
  summary: PreviewSummary;
  differences: DiffItem[];
  parse_warnings: string[];
}

export interface ImportResult {
  success: boolean;
  batch_id: string;
  imported: { new: number; overwritten: number };
  skipped: { duplicates: number; no_match: number; manual_skip: number };
  total_amount_imported: number;
  warnings: string[];
}

export interface BatchRecord {
  id: string;
  imported_at: string;
  period_label: string | null;
  source_file: string | null;
  total_amount: number | null;
  record_count: number | null;
}

export const previewImport = async (
  file: File,
  periodLabel: string,
): Promise<PreviewResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('period_label', periodLabel);
  const res = await client.post('/api/import/proventos/preview', formData);
  return res.data;
};

export const confirmImport = async (
  fileToken: string,
  periodLabel: string,
  forceDuplicates: boolean,
  skipIndices: number[],
  manualMappings: { index: number; instrument_id: number }[],
): Promise<ImportResult> => {
  const res = await client.post('/api/import/proventos/confirm', {
    file_token: fileToken,
    period_label: periodLabel,
    force_duplicates: forceDuplicates,
    skip_indices: skipIndices,
    manual_mappings: manualMappings,
  });
  return res.data;
};

export const mapInstrument = async (
  fileToken: string,
  index: number,
  instrumentId: number,
): Promise<{ ok: boolean }> => {
  const res = await client.post('/api/import/proventos/map-instrument', {
    file_token: fileToken,
    index,
    instrument_id: instrumentId,
  });
  return res.data;
};

export const revertBatch = async (batchId: string): Promise<{ deleted: number; batch_id: string }> => {
  const res = await client.delete(`/api/import/proventos/batch/${batchId}`);
  return res.data;
};

export const getBatches = async (): Promise<BatchRecord[]> => {
  const res = await client.get('/api/import/proventos/batches');
  return res.data;
};
