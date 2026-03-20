import client from './client';

export const getInstrumentHistory = (id: number, dateFrom?: string, dateTo?: string) =>
  client.get(`/api/history/${id}`, { params: { date_from: dateFrom, date_to: dateTo } }).then(r => r.data);

export const compareInstruments = (ids: number[], dateFrom?: string, dateTo?: string) =>
  client.get('/api/history/compare', { params: { ids: ids.join(','), date_from: dateFrom, date_to: dateTo } }).then(r => r.data);
