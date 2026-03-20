import client from './client';

export interface PositionFilters {
  custodian?: string;
  type?: string;
  currency?: string;
  status?: string;
  search?: string;
  sort?: string;
  order?: string;
  page?: number;
  limit?: number;
}

export const getPositions = (filters: PositionFilters = {}) =>
  client.get('/api/positions', { params: filters }).then(r => r.data);

export const exportPositions = (filters: PositionFilters = {}) => {
  const params = new URLSearchParams(filters as any).toString();
  window.open(`http://localhost:8000/api/positions/export?${params}`, '_blank');
};
