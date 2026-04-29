import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../api';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);
  const navigate = useNavigate();

  async function handleLogin(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const res = await authAPI.login(username, password);
      localStorage.setItem('token', res.data.token);
      localStorage.setItem('user',  JSON.stringify({ username: res.data.username, is_admin: res.data.is_admin }));
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || '登入失敗，請確認帳號密碼');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-base)',
    }}>
      <div style={{ width: '100%', maxWidth: 380 }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            width: 52, height: 52, borderRadius: 14,
            background: 'var(--accent-glow)', border: '1px solid rgba(59,130,246,0.3)',
            marginBottom: 16, fontSize: 24
          }}>📈</div>
          <h1 style={{ fontSize: 20, fontWeight: 600, letterSpacing: '-0.5px' }}>台股 AI 分析平台</h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>僅限授權帳號登入</p>
        </div>

        {/* 表單 */}
        <div className="card" style={{ padding: 28 }}>
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label className="form-label">帳號</label>
              <input
                className="input"
                type="text"
                placeholder="輸入帳號"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoFocus
                required
              />
            </div>
            <div className="form-group" style={{ marginBottom: 20 }}>
              <label className="form-label">密碼</label>
              <input
                className="input"
                type="password"
                placeholder="輸入密碼"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
            </div>

            {error && (
              <div style={{
                background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.2)',
                borderRadius: 'var(--radius-sm)', padding: '10px 14px',
                fontSize: 13, color: 'var(--red)', marginBottom: 16
              }}>{error}</div>
            )}

            <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: '100%', justifyContent: 'center', padding: '11px' }}>
              {loading ? <><span className="spinner" style={{ width: 14, height: 14 }}/> 登入中...</> : '登入'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
