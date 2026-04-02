import axios from 'axios';

const client = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 30000,
});

client.interceptors.request.use(config => {
  const env = localStorage.getItem('app_env') || 'production';
  if (env === 'demo') {
    config.headers['X-Env'] = 'demo';
  }
  return config;
});

export default client;
