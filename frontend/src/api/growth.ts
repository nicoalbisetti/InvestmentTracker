import client from './client';

export interface AnnualItem {
  year: number;
  patrimonio_inicio: number | null;
  patrimonio_fin: number | null;
  net_flow: number | null;
  gain: number | null;
  diff: number | null;
  pct_growth: number | null;
  pct_valorization: number | null;
  data_source: 'calculated' | 'legacy';
}

export interface AnnualGrowthResponse {
  items: AnnualItem[];
  metrics: {
    total_invested: number | null;
    total_gained: number | null;
    gain_ratio: number | null;
    cagr: number | null;
  };
}

export interface MonthlyPoint {
  month: number;
  patrimonio: number | null;
  net_flow: number;
  valorizacion_acum: number | null;
}

export interface MonthlyTransaction {
  date: string;
  month: number;
  type: 'aplicacion' | 'rescate';
  amount_brl: number;
  instrument_name: string;
}

export interface MonthlyGrowthResponse {
  year: number;
  months: MonthlyPoint[];
  transactions: MonthlyTransaction[];
  summary: {
    patrimonio_inicio: number | null;
    patrimonio_fin: number | null;
    net_flow_total: number;
    gain_total: number | null;
    pct_net_flow: number | null;
    pct_gain: number | null;
  };
}

export const getAnnualGrowth = (): Promise<AnnualGrowthResponse> =>
  client.get('/api/annual').then(r => r.data);

export const getMonthlyGrowth = (year: number): Promise<MonthlyGrowthResponse> =>
  client.get('/api/annual/monthly', { params: { year } }).then(r => r.data);
