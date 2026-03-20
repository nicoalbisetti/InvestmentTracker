import client from './client';
export const getProventos = (page = 1, limit = 50) =>
  client.get('/api/proventos', { params: { page, limit } }).then(r => r.data);
export const getMonthlyProventos = (year?: number) =>
  client.get('/api/proventos/monthly', { params: { year } }).then(r => r.data);
