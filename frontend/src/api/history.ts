import client from './client';

export const getInstrumentHistory = (id: number, dateFrom?: string, dateTo?: string) =>
  client.get(`/api/history/${id}`, { params: { date_from: dateFrom, date_to: dateTo } }).then(r => r.data);

export const compareInstruments = (ids: number[], dateFrom?: string, dateTo?: string) =>
  client.get('/api/history/compare', { params: { ids: ids.join(','), date_from: dateFrom, date_to: dateTo } }).then(r => r.data);

export type HistoryFilters = {
  custodian?: string;
  type?: string;
  market?: 'brasil' | 'exterior';
};

export type HistoryItem = {
  instrument_id: number;
  name: string;
  custodian: string;
  type: string;
  values: (number | null)[];
};

export type HistoryMonthlyResponse = {
  year: number;
  currency: string;
  months: number[];
  items: HistoryItem[];
  totals: (number | null)[];
};

export type HistoryAnnualResponse = {
  currency: string;
  years: number[];
  items: HistoryItem[];
  totals: (number | null)[];
};

export const getMonthlyHistory = (year: number, currency: string, filters: HistoryFilters = {}) =>
  client.get<HistoryMonthlyResponse>('/api/history/monthly', {
    params: { year, currency, ...filters },
  }).then(r => r.data);

export const getAnnualHistory = (currency: string, filters: HistoryFilters = {}) =>
  client.get<HistoryAnnualResponse>('/api/history/annual', {
    params: { currency, ...filters },
  }).then(r => r.data);
