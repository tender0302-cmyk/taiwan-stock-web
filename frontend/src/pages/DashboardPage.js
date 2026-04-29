import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { stocksAPI, analysisAPI } from '../api';

const SECTORS = ['全部','半導體','電子零組件','金融保險','航運','塑化','鋼鐵','汽車','建材營造','網路通訊','其他'];

function rsiClass(rsi) {
  if (rsi >= 70) return 'rsi-overbought';
  if (rsi <= 30) return 'rsi-oversold';
  return 'rsi-neutral';
}

function changeColor(val) {
  if (!val && val !== 0) return 'flat';
  if (val > 0) return 'up';
  if (val < 0) return 'down';
  return 'flat';
}

export default function DashboardPage() {
  const [stocks,    setStocks]    = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [filter,    setFilter]    = useState('全部');
  const [search,    setSearch]    = useState('');
  const [selected,  setSelected]  = useState(new Set());
  const [analyzing, setAnalyzing] = useState(false);
  const [report,    setReport]    = useState(null);
  const [error,     setError]     = useState('');
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const navigate = useNavigate();

  const loadStocks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await stocksAPI.list();
      setStocks(res.data.stocks || []);
    } catch (e) {
      setError('載入股票資料失敗');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStocks(); }, [loadStocks]);

  const filtered = stocks.filter(s => {
    const matchSector = filter === '全部' || s.sector === filter;
    const matchSearch = !search || s.code.includes(search) || (s.short_name || '').includes(search);
    return matchSector && matchSearch;
  });

  function toggleSelect(code) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else if (next.size < 10) next.add(code);
      return next;
    });
  }

  async function runAnalysis() {
    if (!selected.size) return;
    setAnalyzing(true); setReport(null); setError('');
    try {
      const res = await analysisAPI.analyzeStocks([...selected]);
      setReport(res.data.report);
    } catch (e) {
      setError(e.response?.data?.detail || 'AI 分析失敗');
    } finally {
      setAnalyzing(false);
    }
  }

  function logout() {
    localStorage.clear();
    navigate('/login');
  }

  return (
    <div className="layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>📈 台股 AI</h1>
          <span>分析平台</span>
        </div>
        <Link className="nav-item active" to="/">股票看板</Link>
        <Link className="nav-item" to="/portfolio">持倉管理</Link>
        {user.is_admin && <Link className="nav-item" to="/admin">帳號管理</Link>}
        <div style={{ marginTop: 'auto', borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div className="nav-item" onClick={logout} style={{ color: 'var(--red)' }}>登出</div>
        </div>
      </aside>

      {/* Main */}
      <main className="main-content">
        <div className="page-header">
          <div>
            <div className="page-title">台灣50 + 中型100 成分股</div>
            <div className="page-subtitle">勾選股票後點擊「AI 分析」取得進出場建議</div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn btn-ghost" onClick={loadStocks} disabled={loading}>
              {loading ? '載入中...' : '🔄 更新資料'}
            </button>
            <button className="btn btn-ghost" onClick={() => stocksAPI.clearCache().then(loadStocks)}>
              清除快取
            </button>
          </div>
        </div>

        {/* 篩選列 */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            className="input" placeholder="搜尋代碼或名稱"
            value={search} onChange={e => setSearch(e.target.value)}
            style={{ width: 180 }}
          />
          {SECTORS.map(s => (
            <button
              key={s}
              className="btn btn-ghost"
              style={{ padding: '6px 12px', fontSize: 12,
                background: filter === s ? 'var(--accent-glow)' : '',
                color: filter === s ? 'var(--accent)' : '',
                borderColor: filter === s ? 'rgba(59,130,246,0.3)' : ''
              }}
              onClick={() => setFilter(s)}
            >{s}</button>
          ))}
        </div>

        {/* 勾選工具列 */}
        {selected.size > 0 && (
          <div className="selection-bar">
            <div className="selection-info">
              已選擇 <strong>{selected.size}</strong> 檔（最多10檔）：
              {[...selected].map(c => {
                const s = stocks.find(x => x.code === c);
                return <span key={c} style={{ marginLeft: 6, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{s?.short_name || c}</span>;
              })}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => setSelected(new Set())}>清除</button>
              <button className="btn btn-primary" onClick={runAnalysis} disabled={analyzing}>
                {analyzing ? <><span className="spinner" style={{ width: 13, height: 13 }}/> AI 分析中...</> : `🤖 AI 分析 (${selected.size}檔)`}
              </button>
            </div>
          </div>
        )}

        {error && <div style={{ color: 'var(--red)', fontSize: 13, marginBottom: 12 }}>{error}</div>}

        {/* 分析報告 */}
        {report && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <span className="card-title">🤖 AI 分析報告</span>
              <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => setReport(null)}>關閉</button>
            </div>
            <div className="report-container">
              <ReactMarkdown>{report}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* 股票表格 */}
        {loading ? (
          <div className="loading"><div className="spinner"/><span>載入股票資料中，請稍候...</span></div>
        ) : (
          <div className="card" style={{ padding: 0 }}>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 40 }}></th>
                    <th>股票</th>
                    <th>現價</th>
                    <th>今日</th>
                    <th>近5日</th>
                    <th>RSI</th>
                    <th>KD</th>
                    <th>MACD</th>
                    <th>量能</th>
                    <th>52週</th>
                    <th>本益比</th>
                    <th>產業</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(s => {
                    const isSelected = selected.has(s.code);
                    return (
                      <tr key={s.code}
                        style={{ background: isSelected ? 'rgba(59,130,246,0.06)' : '', cursor: 'pointer' }}
                        onClick={() => toggleSelect(s.code)}
                      >
                        <td className="check-row" onClick={e => e.stopPropagation()}>
                          <input type="checkbox" checked={isSelected} onChange={() => toggleSelect(s.code)} />
                        </td>
                        <td>
                          <div className="td-name">{s.short_name}</div>
                          <div className="td-code">{s.code}</div>
                        </td>
                        <td className="td-price">${s.price?.toLocaleString()}</td>
                        <td className={`td-number ${changeColor(s.change_1d)}`}>
                          {s.change_1d != null ? `${s.change_1d > 0 ? '+' : ''}${s.change_1d.toFixed(2)}%` : '-'}
                        </td>
                        <td className={`td-number ${changeColor(s.change_5d)}`}>
                          {s.change_5d != null ? `${s.change_5d > 0 ? '+' : ''}${s.change_5d.toFixed(2)}%` : '-'}
                        </td>
                        <td className={`td-number ${rsiClass(s.rsi)}`}>{s.rsi}</td>
                        <td className="td-number" style={{ fontSize: 12 }}>{s.k?.toFixed(0)}/{s.d?.toFixed(0)}</td>
                        <td className={`td-number ${s.macd > s.macd_signal ? 'up' : 'down'}`} style={{ fontSize: 12 }}>
                          {s.macd > 0 ? '+' : ''}{s.macd?.toFixed(1)}
                        </td>
                        <td className="td-number" style={{ color: s.vol_ratio > 1.5 ? 'var(--amber)' : 'var(--text-secondary)' }}>
                          {s.vol_ratio?.toFixed(1)}x
                        </td>
                        <td className="td-number" style={{ fontSize: 12 }}>
                          {s['52w_pos'] != null ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                              <div style={{ width: 40, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                                <div style={{ width: `${s['52w_pos']}%`, height: '100%', background: 'var(--accent)' }}/>
                              </div>
                              <span style={{ fontSize: 11 }}>{s['52w_pos']}%</span>
                            </div>
                          ) : '-'}
                        </td>
                        <td className="td-number">{s.pe_ratio ? s.pe_ratio.toFixed(1) : '-'}</td>
                        <td><span className="badge badge-sector">{s.sector}</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
