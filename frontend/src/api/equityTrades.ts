import client from './client';

export interface EquityTradeOut {
  id: number;
  instrument_id: number;
  date: string;
  trade_type: 'compra' | 'venta';
  quantity: number;
  price: number;
  amount_brl: number | null;
  notes: string | null;
  created_at: string;
  instrument_name: string;
  instrument_ticker: string | null;
}

export interface EquityTradeWithRecalc extends EquityTradeOut {
  recalculated_months: number;
  affected_from: string;
}

export interface EquityTradeSummary {
  instrument_id: number;
  instrument_name: string;
  instrument_ticker: string | null;
  total_compras_qty: number;
  total_ventas_qty: number;
  qty_actual: number;
  avg_price_compra: number | null;
  ultimo_precio: number | null;
  pl_no_realizado: number | null;
  pl_no_realizado_pct: number | null;
}

export interface PaginatedTrades {
  items: EquityTradeOut[];
  total: number;
  page: number;
  pages: number;
}

export interface GetTradesParams {
  instrument_id?: number;
  date_from?: string;
  date_to?: string;
  trade_type?: string;
  page?: number;
  limit?: number;
}

export interface EquityTradeCreate {
  instrument_id: number;
  date: string;
  trade_type: 'compra' | 'venta';
  quantity: number;
  price: number;
  notes?: string;
}

export interface EquityTradeUpdate {
  date?: string;
  trade_type?: 'compra' | 'venta';
  quantity?: number;
  price?: number;
  notes?: string;
}

export async function getEquityTrades(params: GetTradesParams = {}): Promise<PaginatedTrades> {
  const res = await client.get('/api/equity-trades/', { params });
  return res.data;
}

export async function createEquityTrade(data: EquityTradeCreate): Promise<EquityTradeWithRecalc> {
  const res = await client.post('/api/equity-trades/', data);
  return res.data;
}

export async function updateEquityTrade(id: number, data: EquityTradeUpdate): Promise<EquityTradeWithRecalc> {
  const res = await client.put(`/api/equity-trades/${id}`, data);
  return res.data;
}

export async function deleteEquityTrade(id: number): Promise<void> {
  await client.delete(`/api/equity-trades/${id}`);
}

export async function getEquityTradeSummary(instrumentId: number): Promise<EquityTradeSummary> {
  const res = await client.get(`/api/equity-trades/summary/${instrumentId}`);
  return res.data;
}
