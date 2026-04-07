import client from './client';

export interface PositionFilters {
  custodian?: string;
  type?: string;
  currency?: string;
  location?: string;
  status?: string;
  search?: string;
  month?: string;
  sort?: string;
  order?: string;
  page?: number;
  limit?: number;
  with_position?: boolean;
}

export const getPositions = (filters: PositionFilters = {}) =>
  client.get('/api/positions', { params: filters }).then(r => r.data);

export const getCustodians = (): Promise<string[]> =>
  client.get('/api/positions/custodians').then(r => r.data);

export const exportPositions = (filters: PositionFilters = {}) => {
  const params = new URLSearchParams(filters as any).toString();
  window.open(`http://127.0.0.1:8000/api/positions/export?${params}`, '_blank');
};
