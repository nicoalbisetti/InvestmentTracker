import client from './client';

export const getTransactions = (params = {}) =>
  client.get('/api/transactions', { params }).then(r => r.data);
export const createTransaction = (data: any) =>
  client.post('/api/transactions', data).then(r => r.data);
export const updateTransaction = (id: number, data: any) =>
  client.put(`/api/transactions/${id}`, data).then(r => r.data);
export const deleteTransaction = (id: number) =>
  client.delete(`/api/transactions/${id}`).then(r => r.data);
