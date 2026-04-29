// API 請求統一管理
import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: BASE_URL });

// 自動帶 JWT token
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token');
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// 401 自動登出
api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export const authAPI = {
  login:          (username, password) => api.post('/api/auth/login', { username, password }),
  me:             ()                   => api.get('/api/auth/me'),
  changePassword: (old_password, new_password) => api.post('/api/auth/change-password', { old_password, new_password }),
  listUsers:      ()                   => api.get('/api/auth/users'),
  createUser:     (username, password) => api.post('/api/auth/users', { username, password }),
  deleteUser:     (id)                 => api.delete(`/api/auth/users/${id}`),
};

export const stocksAPI = {
  list:       ()     => api.get('/api/stocks/list'),
  getOne:     (code) => api.get(`/api/stocks/${code}`),
  clearCache: ()     => api.delete('/api/stocks/cache'),
  // 串流載入：每抓到一檔就呼叫 onStock，全部完成呼叫 onDone
  stream: (token, onStock, onDone, onError) => {
    const BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    const es = new EventSource(`${BASE}/api/stocks/stream?token=${token}`);
    es.onmessage = (e) => {
      if (e.data === '[DONE]') { es.close(); onDone && onDone(); return; }
      try { onStock(JSON.parse(e.data)); } catch {}
    };
    es.onerror = () => { es.close(); onError && onError(); };
    return es;   // 回傳 EventSource，呼叫端可以 .close() 取消
  },
};

export const portfolioAPI = {
  list:   ()         => api.get('/api/portfolio/'),
  add:    (data)     => api.post('/api/portfolio/', data),
  update: (id, data) => api.put(`/api/portfolio/${id}`, data),
  delete: (id)       => api.delete(`/api/portfolio/${id}`),
};

export const analysisAPI = {
  analyzeStocks:    (codes)    => api.post('/api/analysis/stocks', { codes }),
  analyzePortfolio: (holdings) => api.post('/api/analysis/portfolio', { holdings }),
};

export default api;
