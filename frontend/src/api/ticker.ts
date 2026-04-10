import client from './client';

export interface TickerItem {
  ticker: string;
  name: string;
  price: number;
  change_pct: number;
  currency: 'BRL' | 'USD';
}

export interface TickerResponse {
  items: TickerItem[];
  fetched_at: string;
  cached: boolean;
  stale?: boolean;
  error?: string;
}

export const getTickerQuotes = (): Promise<TickerResponse> =>
  client.get('/api/ticker/quotes').then(r => r.data);
