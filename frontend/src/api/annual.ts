import client from './client';
export const getAnnualSummary = () => client.get('/api/annual').then(r => r.data);
