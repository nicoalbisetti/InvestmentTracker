import client from './client';

export const importExcel = (file: File, onProgress?: (pct: number) => void) => {
  const form = new FormData();
  form.append('file', file);
  return client.post('/api/import', form, {
    onUploadProgress: e => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total));
    },
  }).then(r => r.data);
};

export const getImportHistory = () => client.get('/api/import/history').then(r => r.data);
export const getImportDetail = (id: number) => client.get(`/api/import/history/${id}`).then(r => r.data);
