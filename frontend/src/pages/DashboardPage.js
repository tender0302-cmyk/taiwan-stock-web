import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import api, { stocksAPI, analysisAPI } from '../api';
const simAPI = { create: (data) => api.post('/api/simulation/', data) };

const SECTORS = ['全部','半導體','電子零組件','金融保險','航運','塑化','鋼鐵','汽車','建材營造','網路通訊','其他'];

// 可排序欄位設定
const SORT_COLS = [
  { key: 'name',       label: '股票',    align: 'left'   },
  { key: 'price',      label: '現價',    align: 'right'  },
  { key: 'change_1d',  label: '今日',    align: 'right'  },
  { key: 'change_5d',  label: '近5日',   align: 'right'  },
  { key: 'rsi',        label: 'RSI',     align: 'right'  },
  { key: 'k',          label: 'KD',      align: 'right'  },
  { key: 'macd',       label: 'MACD',    align: 'right'  },
  { key: 'vol_ratio',  label: '量能',    align: 'right'  },
  { key: '52w_pos',    label: '52週',    align: 'right'  },
  { key: 'foreign_net',   label: '外資(張)',  align: 'right'  },
  { key: 'trust_net',     label: '投信(張)',  align: 'right'  },
  { key: 'pe_ratio',      label: '本益比',   align: 'right'  },
  { key: 'sector',     label: '產業',    align: 'left'   },
];

function rsiClass(rsi) {
  if (rsi >= 70) return 'rsi-overbought';
  if (rsi <= 30) return 'rsi-oversold';
  return 'rsi-neutral';
}
function changeColor(val) {
  if (!val && val !== 0) return 'flat';
  return val > 0 ? 'up' : val < 0 ? 'down' : 'flat';
}
function fmtNum(val, decimals = 2) {
  if (val == null) return '-';
  const n = Number(val);
  return (n > 0 ? '+' : '') + n.toFixed(decimals);
}
function instColor(val) {
  if (!val && val !== 0) return 'flat';
  return val > 0 ? 'up' : val < 0 ? 'down' : 'flat';
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
  const [sortKey,   setSortKey]   = useState('');
  const [sortDir,   setSortDir]   = useState('desc');
  const [manualCode, setManualCode] = useState('');
  const [manualResult, setManualResult] = useState(null);
  const [manualLoading, setManualLoading] = useState(false);
  const [manualError, setManualError] = useState('');
  const [simModal, setSimModal] = useState(null);  // {code, name, price}
  const [simForm, setSimForm] = useState({ direction:'buy', shares:'', entry_price:'', stop_loss:'', take_profit:'', note:'' });
  const [simLoading, setSimLoading] = useState(false);

  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const navigate = useNavigate();

  async function searchManualCode() {
    const code = manualCode.trim();
    if (!code) return;
    setManualLoading(true); setManualError(''); setManualResult(null);
    try {
      const res = await stocksAPI.getOne(code);
      setManualResult(res.data);
    } catch (e) {
      setManualError(`找不到股票代碼「${code}」，請確認是否正確`);
    } finally {
      setManualLoading(false);
    }
  }

  async function handleQuickSim() {
    if (!simModal || !simForm.shares || !simForm.entry_price) return;
    setSimLoading(true);
    try {
      await simAPI.create({
        code:        simModal.code,
        direction:   simForm.direction,
        shares:      parseFloat(simForm.shares),
        entry_price: parseFloat(simForm.entry_price),
        stop_loss:   simForm.stop_loss   ? parseFloat(simForm.stop_loss)   : null,
        take_profit: simForm.take_profit ? parseFloat(simForm.take_profit) : null,
        note:        simForm.note,
      });
      setSimModal(null);
      setSimForm({ direction:'buy', shares:'', entry_price:'', stop_loss:'', take_profit:'', note:'' });
      alert(`✅ 模擬單已建立！前往「模擬下單」頁面查看。`);
    } catch(e) {
      alert('建立失敗：' + (e.response?.data?.detail || e.message));
    } finally {
      setSimLoading(false);
    }
  }

  const [loadProgress, setLoadProgress] = useState(0);
  const [cacheStatus,  setCacheStatus]  = useState('');

  const loadStocks = useCallback(async () => {
    setLoading(true); setError(''); setLoadProgress(10);
    
    // 輪詢機制：每 8 秒嘗試一次，最多等 3 分鐘
    const maxTries = 22;
    for (let i = 0; i < maxTries; i++) {
      try {
        const res = await stocksAPI.list();
        const fetched = res.data.stocks || [];
        if (fetched.length > 0) {
          setStocks(fetched);
          setCacheStatus(res.data.cache_status || '');
          setLoadProgress(100);
          setLoading(false);
          return;
        }
        // 還沒有資料，更新進度條再等
        setLoadProgress(Math.min(90, 10 + i * 4));
      } catch (e) {
        // 網路錯誤就直接失敗
        setError('載入股票資料失敗，請點「更新資料」重試');
        setLoading(false);
        return;
      }
      // 等 8 秒再重試（最後一次不等）
      if (i < maxTries - 1) {
        await new Promise(r => setTimeout(r, 8000));
      }
    }
    setError('載入超時，請點「更新資料」或「清除快取」重試');
    setLoading(false);
  }, []);

  useEffect(() => { loadStocks(); }, [loadStocks]);

  // 篩選
  const filtered = stocks.filter(s => {
    const matchSector = filter === '全部' || s.sector === filter;
    const matchSearch = !search || s.code.includes(search) || (s.short_name || '').includes(search) || (s.name || '').includes(search);
    return matchSector && matchSearch;
  });

  // 排序
  const sorted = [...filtered].sort((a, b) => {
    if (!sortKey) return 0;
    const av = a[sortKey] ?? (sortDir === 'desc' ? -Infinity : Infinity);
    const bv = b[sortKey] ?? (sortDir === 'desc' ? -Infinity : Infinity);
    if (typeof av === 'string') return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
    return sortDir === 'asc' ? av - bv : bv - av;
  });

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  }

  function SortIcon({ colKey }) {
    if (sortKey !== colKey) return <span style={{ opacity: 0.25, fontSize: 10, marginLeft: 3 }}>⇅</span>;
    return <span style={{ fontSize: 10, marginLeft: 3, color: 'var(--accent)' }}>{sortDir === 'desc' ? '↓' : '↑'}</span>;
  }

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

  function logout() { localStorage.clear(); navigate('/login'); }

  // 欄位標題渲染
  function ThCol({ col }) {
    return (
      <th
        style={{ cursor: 'pointer', userSelect: 'none', textAlign: col.align, whiteSpace: 'nowrap' }}
        onClick={() => handleSort(col.key)}
      >
        {col.label}<SortIcon colKey={col.key} />
      </th>
    );
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
        <Link className="nav-item" to="/simulation">模擬下單</Link>
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
            <div className="page-subtitle">勾選股票後點擊「AI 分析」取得進出場建議｜點欄位標題排序</div>
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
            style={{ width: 160 }}
          />
          {/* 手動輸入代碼查詢（不限台灣50/中型100清單）*/}
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <input
              className="input" placeholder="手動輸入代碼查詢"
              value={manualCode}
              onChange={e => setManualCode(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && searchManualCode()}
              style={{ width: 160 }}
            />
            <button className="btn btn-ghost" style={{ padding: '8px 12px', fontSize: 12 }}
              onClick={searchManualCode} disabled={manualLoading}>
              {manualLoading ? '查詢中...' : '🔍 查詢'}
            </button>
          </div>
          {SECTORS.map(s => (
            <button key={s} className="btn btn-ghost"
              style={{
                padding: '6px 12px', fontSize: 12,
                background: filter === s ? 'var(--accent-glow)' : '',
                color: filter === s ? 'var(--accent)' : '',
                borderColor: filter === s ? 'rgba(59,130,246,0.3)' : ''
              }}
              onClick={() => setFilter(s)}
            >{s}</button>
          ))}
        </div>

        {/* 手動查詢結果 */}
        {manualError && (
          <div style={{ color: 'var(--red)', fontSize: 13, marginBottom: 12 }}>{manualError}</div>
        )}
        {manualResult && (
          <div className="card" style={{ marginBottom: 16, padding: '16px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
                  {manualResult.short_name || manualResult.name}
                </span>
                <span className="td-code" style={{ marginLeft: 8 }}>{manualResult.code}</span>
                <span className="badge badge-sector" style={{ marginLeft: 8 }}>{manualResult.sector}</span>
              </div>
              <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => setManualResult(null)}>關閉</button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12, marginTop: 12 }}>
              {[
                { label: '現價',   value: `$${manualResult.price?.toLocaleString()}` },
                { label: '今日',   value: `${manualResult.change_1d > 0 ? '+' : ''}${manualResult.change_1d?.toFixed(2)}%`, color: manualResult.change_1d >= 0 ? 'var(--red)' : 'var(--green)' },
                { label: '近5日',  value: `${manualResult.change_5d > 0 ? '+' : ''}${manualResult.change_5d?.toFixed(2)}%`, color: manualResult.change_5d >= 0 ? 'var(--red)' : 'var(--green)' },
                { label: 'RSI',    value: manualResult.rsi },
                { label: 'KD',     value: `${manualResult.k?.toFixed(0)}/${manualResult.d?.toFixed(0)}` },
                { label: 'MACD',   value: manualResult.macd?.toFixed(2) },
                { label: '量能',   value: `${manualResult.vol_ratio?.toFixed(1)}x` },
                { label: '52週位置', value: manualResult['52w_pos'] != null ? `${manualResult['52w_pos']}%` : '-' },
                { label: '外資',   value: manualResult.foreign_net != null ? `${manualResult.foreign_net > 0 ? '+' : ''}${manualResult.foreign_net?.toLocaleString()}張` : '-' },
                { label: '投信',   value: manualResult.trust_net != null ? `${manualResult.trust_net > 0 ? '+' : ''}${manualResult.trust_net?.toLocaleString()}張` : '-' },
                { label: '本益比', value: manualResult.pe_ratio?.toFixed(1) || '-' },
                { label: '市值',   value: `${manualResult.market_cap_b?.toFixed(0)}億` },
              ].map(item => (
                <div key={item.label} style={{ background: 'var(--bg-base)', borderRadius: 6, padding: '8px 12px' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3 }}>{item.label}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, fontFamily: 'var(--font-mono)', color: item.color || 'var(--text-primary)' }}>{item.value}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn btn-ghost" style={{ fontSize: 12 }}
                onClick={() => {
                  const code = manualResult.code;
                  // 加入股池（表格）
                  setStocks(prev => prev.find(s => s.code === code) ? prev : [manualResult, ...prev]);
                  // 同時選取
                  toggleSelect(code);
                }}>
                {stocks.find(s => s.code === manualResult.code) ? '✓ 已加入股池' : '📋 加入股池'}
              </button>
              <button className="btn btn-ghost" style={{ fontSize: 12 }}
                onClick={() => {
                  setSimModal({ code: manualResult.code, name: manualResult.short_name || manualResult.name, price: manualResult.price });
                  setSimForm(f => ({ ...f, entry_price: String(manualResult.price || '') }));
                }}>
                🎯 模擬下單
              </button>
            </div>
          </div>
        )}

        {/* 勾選工具列 */}
        {selected.size > 0 && (
          <div className="selection-bar">
            <div className="selection-info">
              已選擇 <strong>{selected.size}</strong> 檔（最多10檔）：
              {[...selected].map(c => {
                const s = stocks.find(x => x.code === c);
                return (
                  <span key={c} style={{ marginLeft: 6, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                    {s?.short_name || c}
                  </span>
                );
              })}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => setSelected(new Set())}>清除</button>
              <button className="btn btn-primary" onClick={runAnalysis} disabled={analyzing}>
                {analyzing
                  ? <><span className="spinner" style={{ width: 13, height: 13 }}/> AI 分析中（含市場新聞）...</>
                  : `🤖 AI 分析 (${selected.size}檔)`
                }
              </button>
            </div>
          </div>
        )}

        {error && <div style={{ color: 'var(--red)', fontSize: 13, marginBottom: 12 }}>{error}</div>}

        {/* 分析報告 */}
        {report && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <span className="card-title">🤖 AI 分析報告（含市場新聞情緒）</span>
              <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => setReport(null)}>關閉</button>
            </div>
            <div className="report-container">
              <ReactMarkdown>{report}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* 股票表格 */}
        {loading ? (
          <div className="loading">
            <div className="spinner"/>
            <div style={{ textAlign: 'center' }}>
              <div>載入股票資料中（首次可能需要 30-60 秒）...</div>
              <div style={{ marginTop: 12, width: 200, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden', margin: '12px auto 0' }}>
                <div style={{ width: `${loadProgress}%`, height: '100%', background: 'var(--accent)', transition: 'width 0.3s' }}/>
              </div>
              <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-muted)' }}>{loadProgress}%</div>
            </div>
          </div>
        ) : (
          <div className="card" style={{ padding: 0 }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>
                顯示 {sorted.length} 檔（共 {stocks.length} 檔）｜點欄位標題可排序
                {sortKey && <span style={{ marginLeft: 8, color: 'var(--accent)' }}>排序：{SORT_COLS.find(c=>c.key===sortKey)?.label} {sortDir === 'desc' ? '↓' : '↑'}</span>}
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                {cacheStatus && <span style={{ marginRight: 8 }}>{cacheStatus}</span>}
                {loadProgress < 100 && stocks.length > 0 && (
                  <span style={{ color: 'var(--amber)', marginRight: 8 }}>⏳ 載入中 {loadProgress}%</span>
                )}
                <span title="法人買賣超資料由證交所每日收盤後約17:00發布，因此外資/投信欄位為前一交易日資料，股價為即時資料，屬正常現象">
                  ⚠️ 法人資料為前一交易日（收盤後更新）
                </span>
              </span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 40 }}></th>
                    {SORT_COLS.map(col => <ThCol key={col.key} col={col} />)}
                  </tr>
                </thead>
                <tbody>
                  {sorted.map(s => {
                    const isSelected = selected.has(s.code);
                    return (
                      <tr key={s.code}
                        style={{ background: isSelected ? 'rgba(59,130,246,0.06)' : '', cursor: 'pointer' }}
                        onClick={() => toggleSelect(s.code)}
                      >
                        <td className="check-row" onClick={e => e.stopPropagation()}
                          style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '12px 8px' }}>
                          <input type="checkbox" checked={isSelected} onChange={() => toggleSelect(s.code)} />
                          <button
                            title="快速模擬下單"
                            style={{
                              background: 'none', border: '1px solid var(--border)',
                              borderRadius: 4, cursor: 'pointer', fontSize: 11,
                              color: 'var(--text-muted)', padding: '2px 5px',
                              lineHeight: 1,
                            }}
                            onClick={e => {
                              e.stopPropagation();
                              setSimModal({ code: s.code, name: s.short_name || s.name, price: s.price });
                              setSimForm(f => ({ ...f, entry_price: String(s.price || '') }));
                            }}
                          >模擬</button>
                        </td>
                        {/* 股票名稱 */}
                        <td>
                          <div className="td-name">{s.short_name || s.name}</div>
                          <div className="td-code">{s.code}</div>
                        </td>
                        {/* 現價 */}
                        <td className="td-price" style={{ textAlign: 'right' }}>${s.price?.toLocaleString()}</td>
                        {/* 今日 */}
                        <td className={`td-number ${changeColor(s.change_1d)}`} style={{ textAlign: 'right' }}>
                          {s.change_1d != null ? `${fmtNum(s.change_1d)}%` : '-'}
                        </td>
                        {/* 近5日 */}
                        <td className={`td-number ${changeColor(s.change_5d)}`} style={{ textAlign: 'right' }}>
                          {s.change_5d != null ? `${fmtNum(s.change_5d)}%` : '-'}
                        </td>
                        {/* RSI */}
                        <td className={`td-number ${rsiClass(s.rsi)}`} style={{ textAlign: 'right' }}>{s.rsi}</td>
                        {/* KD */}
                        <td className="td-number" style={{ textAlign: 'right', fontSize: 12 }}>
                          {s.k?.toFixed(0)}/{s.d?.toFixed(0)}
                        </td>
                        {/* MACD */}
                        <td className={`td-number ${s.macd > s.macd_signal ? 'up' : 'down'}`} style={{ textAlign: 'right', fontSize: 12 }}>
                          {s.macd > 0 ? '+' : ''}{s.macd?.toFixed(1)}
                        </td>
                        {/* 量能 */}
                        <td className="td-number" style={{ textAlign: 'right', color: s.vol_ratio > 1.5 ? 'var(--amber)' : 'var(--text-secondary)' }}>
                          {s.vol_ratio?.toFixed(1)}x
                        </td>
                        {/* 52週位置 */}
                        <td style={{ textAlign: 'right' }}>
                          {s['52w_pos'] != null ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}>
                              <div style={{ width: 36, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                                <div style={{ width: `${s['52w_pos']}%`, height: '100%', background: 'var(--accent)' }}/>
                              </div>
                              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>{s['52w_pos']}%</span>
                            </div>
                          ) : '-'}
                        </td>
                        {/* 外資（單位：張，為前一交易日資料） */}
                        <td className={`td-number ${instColor(s.foreign_net)}`} style={{ textAlign: 'right', fontSize: 12 }}>
                          {s.foreign_net != null && s.foreign_net !== 0
                            ? `${s.foreign_net > 0 ? '+' : ''}${s.foreign_net.toLocaleString()}`
                            : <span style={{color:'var(--text-muted)'}}>-</span>}
                        </td>
                        {/* 投信（單位：張，為前一交易日資料） */}
                        <td className={`td-number ${instColor(s.trust_net)}`} style={{ textAlign: 'right', fontSize: 12 }}>
                          {s.trust_net != null && s.trust_net !== 0
                            ? `${s.trust_net > 0 ? '+' : ''}${s.trust_net.toLocaleString()}`
                            : <span style={{color:'var(--text-muted)'}}>-</span>}
                        </td>

                        {/* 本益比 */}
                        <td className="td-number" style={{ textAlign: 'right' }}>{s.pe_ratio ? s.pe_ratio.toFixed(1) : '-'}</td>
                        {/* 產業 */}
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
