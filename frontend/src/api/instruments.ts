import client from './client';
export const getInstruments = (params = {}) =>
  client.get('/api/instruments', { params }).then(r => r.data);
export const updateInstrument = (id: number, data: any) =>
  client.put(`/api/instruments/${id}`, data).then(r => r.data);

export async function createInstrument(data: {
  name: string;
  custodian: string;
  type: string;
  currency: string;
  status: string;
  location: string;
  liquidity?: string;
  maturity_date?: string;
  index_type?: string;
  asset_class?: string;
  balance_brl?: number;
  initial_period?: string;
}): Promise<{
  id: number;
  name: string;
  position_created: boolean;
  balance_usd: number | null;
  warnings: string[];
  message: string;
}> {
  const res = await client.post('/api/instruments', data);
  return res.data;
}

export async function rescateTotal(
  instrumentId: number,
  date: string
): Promise<{ message: string; transaction_id: number }> {
  try {
    const res = await client.post(`/api/instruments/${instrumentId}/rescate-total`, { date });
    return res.data;
  } catch (err: any) {
    const msg = err?.response?.data?.detail || 'Error al procesar el rescate.';
    throw new Error(msg);
  }
}
