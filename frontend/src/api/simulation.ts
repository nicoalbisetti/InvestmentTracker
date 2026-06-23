import client from './client';

export interface SimulationParams {
  horizon_months: number;
  monthly_contribution_brl: number;
  rate_renta_fija: number;
  rate_accion: number;
  rate_fii: number;
  rate_fundo: number;
  rate_internacional: number;
}

export interface SimulationDataPoint {
  month: number;
  date: string;
  total: number;
  renta_fija: number;
  accion: number;
  fii: number;
  fundo: number;
  internacional: number;
}

export interface SimulationResult {
  snapshot_date: string;
  initial_total_brl: number;
  data: SimulationDataPoint[];
}

export const DEFAULT_PARAMS: SimulationParams = {
  horizon_months: 60,
  monthly_contribution_brl: 0,
  rate_renta_fija: 0.13,
  rate_accion: 0.12,
  rate_fii: 0.10,
  rate_fundo: 0.11,
  rate_internacional: 0.10,
};

export const CLASS_LABELS: Record<string, string> = {
  renta_fija: 'Renta Fija',
  accion: 'Ações / ETFs',
  fii: 'FIIs',
  fundo: 'Fondos',
  internacional: 'Internacional',
};

export async function fetchSimulation(params: SimulationParams): Promise<SimulationResult> {
  const res = await client.get('/api/simulation', { params });
  return res.data;
}
