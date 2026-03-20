import client from './client';
export const getInstruments = (params = {}) =>
  client.get('/api/instruments', { params }).then(r => r.data);
export const updateInstrument = (id: number, data: any) =>
  client.put(`/api/instruments/${id}`, data).then(r => r.data);
