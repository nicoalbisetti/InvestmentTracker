import client from './client';

export const getDashboardKPIs = () => client.get('/api/dashboard/kpis').then(r => r.data);
export const getEvolution = (range = 'all', currency = 'BRL') =>
  client.get('/api/dashboard/evolution', { params: { range, currency } }).then(r => r.data);
export const getDistribution = () => client.get('/api/dashboard/distribution').then(r => r.data);
export const getTopBottom = () => client.get('/api/dashboard/top-bottom').then(r => r.data);
