import api from './client';

export interface QuoteData {
  date: string;
  usd_brl: number;
  bvmf3_price: number | null;
}

export async function getQuotes(date_from?: string, date_to?: string): Promise<QuoteData[]> {
  const params = new URLSearchParams();
  if (date_from) params.append('date_from', date_from);
  if (date_to) params.append('date_to', date_to);
  const res = await api.get(`/quotes?${params.toString()}`);
  return res.data;
}

export async function createQuote(date: string, usd_brl: number, bvmf3_price?: number): Promise<{message: string, date: string}> {
  const payload: any = { quote_date: date, usd_brl };
  if (bvmf3_price !== undefined) payload.bvmf3_price = bvmf3_price;
  const res = await api.post('/quotes', payload);
  return res.data;
}
