import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { portfolioAPI, analysisAPI, stocksAPI } from '../api';

export default function PortfolioPage() {
  const [holdings,  setHoldings]  = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [report,    setReport]    = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editItem,  setEditItem]  = useState(null);
  const [toast,     setToast]     = useState(null);
  const [form, setForm] = useState({ code: '', shares: 1, cost: '', buy_date: '', note: '' });
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const navigate = useNavigate();

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const loadHoldings = useCallback(async () => {
    setLoading(true);
    try {
      const res = await portfolioAPI.list();
      setHoldings(res.data || []);
    } catch (e) {
      showToast('載入持倉失敗', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadHoldings(); }, [loadHoldings]);

  // 自動帶入股票名稱
  async function handleCodeBlur() {
    if (!form.code || form.code.length < 4) return;
    try {
      const res = await stocksAPI.getOne(form.code);
      setForm(f => ({ ...f, _name: res.data.short_name }));
    } catch (e) {}
  }

  async function handleSave() {
    if (!form.code || !form.cost || !form.buy_date) {
      showToast('請填入必要欄位', 'error');
      return;
    }
    try {
      if (editItem) {
        await portfolioAPI.update(editItem.id, {
          shares:   parseInt(form.shares),
          cost:     parseFloat(form.cost),
          buy_date: form.buy_date,
          note:     form.note,
        });
        showToast('更新成功');
      } else {
        await portfolioAPI.add({
          code:     form.code,
          shares:   parseInt(form.shares),
          cost:     parseFloat(form.cost),
          buy_date: form.buy_date,
          note:     form.note,
        });
        showToast('新增成功');
      }
      setShowModal(false);
      setEditItem(null);
      setForm({ code: '', shares: 1, cost: '', buy_date: '', note: '' });
      loadHoldings();
    } catch (e) {
      showToast(e.response?.data?.detail || '操作失敗', 'error');
    }
  }

  async function handleDelete(id, name) {
    if (!window.confirm(`確認刪除 ${name}？`)) return;
    try {
      await portfolioAPI.delete(id);
      showToast(`已刪除 ${name}`);
      loadHoldings();
    } catch (e) {
      showToast('刪除失敗', 'error');
    }
  }

  function openEdit(h) {
    setEditItem(h);
    setForm({ code: h.code, shares: h.shares, cost: h.cost, buy_date: h.buy_date, note: h.note || '' });
    setShowModal(true);
  }

  async function runPortfolioAnalysis() {
    if (!holdings.length) return;
    setAnalyzing(true); setReport(null);
    try {
      const res = await analysisAPI.analyzePortfolio(holdings);
      setReport(res.data.report);
    } catch (e) {
      showToast('AI 分析失敗', 'error');
    } finally {
      setAnalyzing(false);
    }
  }

  // 統計
  const totalCost  = holdings.reduce((s, h) => s + (h.cost_total || 0), 0);
  const totalValue = holdings.reduce((s, h) => s + (h.value_now || 0), 0);
  const totalPnl   = totalValue - totalCost;
  const totalPct   = totalCost > 0 ? totalPnl / totalCost * 100 : 0;

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>📈 台股 AI</h1>
          <span>分析平台</span>
        </div>
        <Link className="nav-item" to="/">股票看板</Link>
        <Link className="nav-item active" to="/portfolio">持倉管理</Link>
        {user.is_admin && <Link className="nav-item" to="/admin">帳號管理</Link>}
        <div style={{ marginTop: 'auto', borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div className="nav-item" onClick={() => { localStorage.clear(); navigate('/login'); }} style={{ color: 'var(--red)' }}>登出</div>
        </div>
      </aside>

      <main className="main-content">
        <div className="page-header">
          <div>
            <div className="page-title">持倉管理</div>
            <div className="page-subtitle">管理持有股票，取得 AI 健康檢查報告</div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn btn-ghost" onClick={runPortfolioAnalysis} disabled={analyzing || !holdings.length}>
              {analyzing ? <><span className="spinner" style={{ width: 13, height: 13 }}/> 分析中...</> : '🤖 AI 持倉分析'}
            </button>
            <button className="btn btn-primary" onClick={() => { setEditItem(null); setForm({ code:'', shares:1, cost:'', buy_date:'', note:'' }); setShowModal(true); }}>
              + 新增持倉
            </button>
          </div>
        </div>

        {/* 統計卡 */}
        <div className="stat-row">
          <div className="stat-card">
            <div className="stat-label">持倉檔數</div>
            <div className="stat-value">{holdings.length}</div>
            <div className="stat-sub">支股票</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">總投入成本</div>
            <div className="stat-value">${totalCost.toLocaleString('zh-TW', { maximumFractionDigits: 0 })}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">目前市值</div>
            <div className="stat-value">${totalValue.toLocaleString('zh-TW', { maximumFractionDigits: 0 })}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">整體損益</div>
            <div className="stat-value" style={{ color: totalPnl >= 0 ? 'var(--red)' : 'var(--green)' }}>
              {totalPct >= 0 ? '+' : ''}{totalPct.toFixed(2)}%
            </div>
            <div className="stat-sub" style={{ color: totalPnl >= 0 ? 'var(--red)' : 'var(--green)' }}>
              {totalPnl >= 0 ? '+' : ''}{totalPnl.toLocaleString('zh-TW', { maximumFractionDigits: 0 })} 元
            </div>
          </div>
        </div>

        {/* 分析報告 */}
        {report && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <span className="card-title">💼 AI 持倉健康檢查報告</span>
              <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => setReport(null)}>關閉</button>
            </div>
            <div className="report-container">
              <ReactMarkdown>{report}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* 持倉表格 */}
        {loading ? (
          <div className="loading"><div className="spinner"/><span>載入中...</span></div>
        ) : holdings.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>
            還沒有持倉記錄，點擊「新增持倉」開始追蹤
          </div>
        ) : (
          <div className="card" style={{ padding: 0 }}>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>股票</th>
                    <th>張數</th>
                    <th>成本價</th>
                    <th>現價</th>
                    <th>損益</th>
                    <th>今日</th>
                    <th>市值</th>
                    <th>持有天數</th>
                    <th>買入日</th>
                    <th>備註</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map(h => {
                    const pnlColor = (h.pnl_pct || 0) >= 0 ? 'up' : 'down';
                    return (
                      <tr key={h.id}>
                        <td>
                          <div className="td-name">{h.name}</div>
                          <div className="td-code">{h.code}</div>
                        </td>
                        <td className="td-number">{h.shares} 張</td>
                        <td className="td-number">${h.cost.toLocaleString()}</td>
                        <td className="td-price">{h.current_price != null ? `$${h.current_price.toLocaleString()}` : '-'}</td>
                        <td className={`td-number ${pnlColor}`}>
                          {h.pnl_pct != null ? `${h.pnl_pct >= 0 ? '+' : ''}${h.pnl_pct.toFixed(2)}%` : '-'}
                          {h.pnl_amt != null && (
                            <div style={{ fontSize: 11 }}>
                              {h.pnl_amt >= 0 ? '+' : ''}{h.pnl_amt.toLocaleString()}
                            </div>
                          )}
                        </td>
                        <td className={`td-number ${(h.change_1d || 0) >= 0 ? 'up' : 'down'}`}>
                          {h.change_1d != null ? `${h.change_1d >= 0 ? '+' : ''}${h.change_1d.toFixed(2)}%` : '-'}
                        </td>
                        <td className="td-number">{h.value_now != null ? `$${h.value_now.toLocaleString()}` : '-'}</td>
                        <td className="td-number">{h.hold_days} 天</td>
                        <td className="td-number" style={{ fontSize: 12 }}>{h.buy_date}</td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 100 }}>{h.note || '-'}</td>
                        <td>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => openEdit(h)}>編輯</button>
                            <button className="btn btn-danger" style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => handleDelete(h.id, h.name)}>刪除</button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* 新增/編輯 Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>{editItem ? '編輯持倉' : '新增持倉'}</h2>

            <div className="form-group">
              <label className="form-label">股票代碼 *</label>
              <input
                className="input"
                placeholder="例如：2330"
                value={form.code}
                onChange={e => setForm(f => ({ ...f, code: e.target.value }))}
                onBlur={handleCodeBlur}
                disabled={!!editItem}
              />
              {form._name && <div style={{ fontSize: 12, color: 'var(--accent)', marginTop: 4 }}>✓ {form._name}</div>}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">持有張數 *</label>
                <input className="input" type="number" min="1" value={form.shares} onChange={e => setForm(f => ({ ...f, shares: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">買入成本（每股）*</label>
                <input className="input" type="number" step="0.1" placeholder="元" value={form.cost} onChange={e => setForm(f => ({ ...f, cost: e.target.value }))} />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">買入日期 *</label>
              <input className="input" type="date" value={form.buy_date} onChange={e => setForm(f => ({ ...f, buy_date: e.target.value }))} />
            </div>

            <div className="form-group">
              <label className="form-label">備註</label>
              <input className="input" placeholder="選填" value={form.note} onChange={e => setForm(f => ({ ...f, note: e.target.value }))} />
            </div>

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
              <button className="btn btn-ghost" onClick={() => setShowModal(false)}>取消</button>
              <button className="btn btn-primary" onClick={handleSave}>
                {editItem ? '儲存' : '新增'}
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
    </div>
  );
}
