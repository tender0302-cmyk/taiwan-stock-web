import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import api, { stocksAPI } from '../api';

// 模擬下單 API
const simAPI = {
  list:   (status = 'open') => api.get(`/api/simulation/?status=${status}`),
  create: (data)            => api.post('/api/simulation/', data),
  update: (id, data)        => api.put(`/api/simulation/${id}`, data),
  close:  (id, price)       => api.post(`/api/simulation/${id}/close?close_price=${price}`),
  delete: (id)              => api.delete(`/api/simulation/${id}`),
};

const DIRECTION_LABEL = { buy: '做多 📈', sell: '做空 📉' };
const DIRECTION_COLOR = { buy: 'var(--red)', sell: 'var(--green)' };

export default function SimulationPage() {
  const [orders,    setOrders]    = useState([]);
  const [history,   setHistory]   = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [showTab,   setShowTab]   = useState('open');    // 'open' | 'closed'
  const [showModal, setShowModal] = useState(false);
  const [closeModal, setCloseModal] = useState(null);   // {id, name, price}
  const [closePrice, setClosePrice] = useState('');
  const [toast,     setToast]     = useState(null);
  const [searching, setSearching] = useState(false);
  const [searchResult, setSearchResult] = useState(null);

  const [form, setForm] = useState({
    code: '', direction: 'buy', shares: '',
    entry_price: '', stop_loss: '', take_profit: '', note: '',
    _name: '', _price: '',
  });

  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const navigate = useNavigate();

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const loadOrders = useCallback(async () => {
    setLoading(true);
    try {
      const [openRes, closedRes] = await Promise.all([
        simAPI.list('open'),
        simAPI.list('closed'),
      ]);
      setOrders(openRes.data  || []);
      setHistory(closedRes.data || []);
    } catch (e) {
      showToast('載入失敗', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadOrders(); }, [loadOrders]);

  // 輸入代碼後查詢現價
  async function handleCodeSearch() {
    const code = form.code.trim();
    if (!code) return;
    setSearching(true);
    try {
      const res = await stocksAPI.getOne(code);
      const s   = res.data;
      setForm(f => ({
        ...f,
        _name:       s.short_name || s.name || code,
        _price:      s.price,
        entry_price: String(s.price),
      }));
      setSearchResult(s);
    } catch (e) {
      showToast(`找不到股票代碼 ${code}`, 'error');
      setSearchResult(null);
    } finally {
      setSearching(false);
    }
  }

  async function handleCreate() {
    if (!form.code || !form.shares || !form.entry_price) {
      showToast('請填入代碼、股數、進場價', 'error'); return;
    }
    try {
      const res = await simAPI.create({
        code:        form.code.trim(),
        direction:   form.direction,
        shares:      parseFloat(form.shares),
        entry_price: parseFloat(form.entry_price),
        stop_loss:   form.stop_loss   ? parseFloat(form.stop_loss)   : null,
        take_profit: form.take_profit ? parseFloat(form.take_profit) : null,
        note:        form.note,
      });
      showToast(res.data.message);
      setShowModal(false);
      setForm({ code:'', direction:'buy', shares:'', entry_price:'', stop_loss:'', take_profit:'', note:'', _name:'', _price:'' });
      setSearchResult(null);
      loadOrders();
    } catch (e) {
      showToast(e.response?.data?.detail || '新增失敗', 'error');
    }
  }

  async function handleClose() {
    if (!closePrice) { showToast('請輸入平倉價格', 'error'); return; }
    try {
      const res = await simAPI.close(closeModal.id, parseFloat(closePrice));
      showToast(`平倉完成｜損益 ${res.data.pnl_pct > 0 ? '+' : ''}${res.data.pnl_pct}% (${res.data.pnl_amount > 0 ? '+' : ''}${res.data.pnl_amount.toLocaleString()}元)`);
      setCloseModal(null);
      setClosePrice('');
      loadOrders();
    } catch (e) {
      showToast('平倉失敗', 'error');
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('確認刪除這筆模擬單？')) return;
    await simAPI.delete(id);
    showToast('已刪除');
    loadOrders();
  }

  // 統計
  const totalPnl     = orders.reduce((s, o) => s + (o.pnl_amount || 0), 0);
  const totalEntry   = orders.reduce((s, o) => s + (o.entry_value || 0), 0);
  const realizedPnl  = history.reduce((s, o) => s + (o.pnl_amount || 0), 0);
  const pnlColor     = (v) => (v || 0) >= 0 ? 'var(--red)' : 'var(--green)';

  const displayOrders = showTab === 'open' ? orders : history;

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo"><h1>📈 台股 AI</h1><span>分析平台</span></div>
        <Link className="nav-item" to="/">股票看板</Link>
        <Link className="nav-item" to="/portfolio">持倉管理</Link>
        <Link className="nav-item active" to="/simulation">模擬下單</Link>
        {user.is_admin && <Link className="nav-item" to="/admin">帳號管理</Link>}
        <div style={{ marginTop: 'auto', borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div className="nav-item" onClick={() => { localStorage.clear(); navigate('/login'); }} style={{ color: 'var(--red)' }}>登出</div>
        </div>
      </aside>

      <main className="main-content">
        <div className="page-header">
          <div>
            <div className="page-title">模擬下單</div>
            <div className="page-subtitle">練習交易策略，不動用真實資金｜與持倉管理完全分開</div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>+ 建立模擬單</button>
        </div>

        {/* 統計卡 */}
        <div className="stat-row">
          <div className="stat-card">
            <div className="stat-label">持倉中</div>
            <div className="stat-value">{orders.length}</div>
            <div className="stat-sub">筆模擬單</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">模擬持倉總額</div>
            <div className="stat-value">${totalEntry.toLocaleString('zh-TW', {maximumFractionDigits:0})}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">浮動損益</div>
            <div className="stat-value" style={{color: pnlColor(totalPnl)}}>
              {totalPnl >= 0 ? '+' : ''}{totalPnl.toLocaleString('zh-TW', {maximumFractionDigits:0})} 元
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">已實現損益</div>
            <div className="stat-value" style={{color: pnlColor(realizedPnl)}}>
              {realizedPnl >= 0 ? '+' : ''}{realizedPnl.toLocaleString('zh-TW', {maximumFractionDigits:0})} 元
            </div>
            <div className="stat-sub">{history.length} 筆已平倉</div>
          </div>
        </div>

        {/* Tab 切換 */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
          {['open', 'closed'].map(tab => (
            <button key={tab} className="btn btn-ghost"
              style={{
                padding: '8px 20px',
                background: showTab === tab ? 'var(--accent-glow)' : '',
                color: showTab === tab ? 'var(--accent)' : '',
                borderColor: showTab === tab ? 'rgba(59,130,246,0.3)' : '',
              }}
              onClick={() => setShowTab(tab)}
            >
              {tab === 'open' ? `持倉中 (${orders.length})` : `已平倉 (${history.length})`}
            </button>
          ))}
        </div>

        {/* 模擬單表格 */}
        {loading ? (
          <div className="loading"><div className="spinner"/><span>載入中...</span></div>
        ) : displayOrders.length === 0 ? (
          <div className="card" style={{textAlign:'center', padding:48, color:'var(--text-muted)'}}>
            {showTab === 'open' ? '還沒有模擬持倉，點擊「建立模擬單」開始練習' : '還沒有已平倉記錄'}
          </div>
        ) : (
          <div className="card" style={{padding:0}}>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>股票</th>
                    <th>方向</th>
                    <th style={{textAlign:'right'}}>股數</th>
                    <th style={{textAlign:'right'}}>進場價</th>
                    <th style={{textAlign:'right'}}>現價</th>
                    <th style={{textAlign:'right'}}>損益</th>
                    <th style={{textAlign:'right'}}>停損</th>
                    <th style={{textAlign:'right'}}>停利</th>
                    <th style={{textAlign:'right'}}>持有天</th>
                    <th>備註</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {displayOrders.map(o => {
                    const warn = o.stop_loss_triggered || o.take_profit_triggered;
                    return (
                      <tr key={o.id} style={{background: warn ? 'rgba(245,158,11,0.05)' : ''}}>
                        <td>
                          <div className="td-name">{o.name}</div>
                          <div className="td-code">{o.code}</div>
                        </td>
                        <td>
                          <span style={{
                            color: DIRECTION_COLOR[o.direction],
                            fontSize: 12, fontWeight: 600,
                            background: o.direction === 'buy' ? 'var(--red-dim)' : 'var(--green-dim)',
                            padding: '2px 8px', borderRadius: 4,
                          }}>
                            {DIRECTION_LABEL[o.direction]}
                          </span>
                        </td>
                        <td className="td-number" style={{textAlign:'right'}}>{Number(o.shares).toLocaleString()} 股</td>
                        <td className="td-number" style={{textAlign:'right'}}>${Number(o.entry_price).toLocaleString()}</td>
                        <td className="td-price" style={{textAlign:'right'}}>
                          {o.current_price != null ? `$${Number(o.current_price).toLocaleString()}` : '-'}
                        </td>
                        <td style={{textAlign:'right'}}>
                          {o.pnl_pct != null ? (
                            <>
                              <div className="td-number" style={{color: pnlColor(o.pnl_pct)}}>
                                {o.pnl_pct >= 0 ? '+' : ''}{o.pnl_pct.toFixed(2)}%
                              </div>
                              <div style={{fontSize:11, fontFamily:'var(--font-mono)', color: pnlColor(o.pnl_amount)}}>
                                {o.pnl_amount >= 0 ? '+' : ''}{Number(o.pnl_amount).toLocaleString()}
                              </div>
                            </>
                          ) : '-'}
                        </td>
                        <td className="td-number" style={{textAlign:'right', fontSize:12}}>
                          {o.stop_loss ? (
                            <span style={{color: o.stop_loss_triggered ? 'var(--amber)' : 'var(--text-secondary)'}}>
                              ${Number(o.stop_loss).toLocaleString()}
                              {o.stop_loss_triggered && ' ⚠️'}
                            </span>
                          ) : '-'}
                        </td>
                        <td className="td-number" style={{textAlign:'right', fontSize:12}}>
                          {o.take_profit ? (
                            <span style={{color: o.take_profit_triggered ? 'var(--green)' : 'var(--text-secondary)'}}>
                              ${Number(o.take_profit).toLocaleString()}
                              {o.take_profit_triggered && ' 🎯'}
                            </span>
                          ) : '-'}
                        </td>
                        <td className="td-number" style={{textAlign:'right'}}>{o.hold_days}天</td>
                        <td style={{fontSize:12, color:'var(--text-muted)'}}>{o.note || '-'}</td>
                        <td>
                          {o.status === 'open' ? (
                            <div style={{display:'flex', gap:4}}>
                              <button className="btn btn-success" style={{padding:'4px 8px', fontSize:11}}
                                onClick={() => { setCloseModal({id:o.id, name:o.name, price:o.current_price}); setClosePrice(String(o.current_price || '')); }}>
                                平倉
                              </button>
                              <button className="btn btn-danger" style={{padding:'4px 8px', fontSize:11}}
                                onClick={() => handleDelete(o.id)}>
                                刪除
                              </button>
                            </div>
                          ) : (
                            <button className="btn btn-danger" style={{padding:'4px 8px', fontSize:11}}
                              onClick={() => handleDelete(o.id)}>
                              刪除
                            </button>
                          )}
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

      {/* 建立模擬單 Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" style={{maxWidth:560}} onClick={e => e.stopPropagation()}>
            <h2>建立模擬單</h2>

            {/* 代碼查詢 */}
            <div className="form-group">
              <label className="form-label">股票代碼 *</label>
              <div style={{display:'flex', gap:8}}>
                <input className="input" placeholder="輸入代碼，如：2330" style={{flex:1}}
                  value={form.code}
                  onChange={e => setForm(f => ({...f, code:e.target.value, _name:'', _price:''}))}
                  onKeyDown={e => e.key === 'Enter' && handleCodeSearch()}
                />
                <button className="btn btn-ghost" onClick={handleCodeSearch} disabled={searching}>
                  {searching ? '查詢中...' : '查詢'}
                </button>
              </div>
              {form._name && (
                <div style={{fontSize:13, color:'var(--accent)', marginTop:4}}>
                  ✓ {form._name}｜現價 ${Number(form._price).toLocaleString()}
                </div>
              )}
            </div>

            {/* 買多/做空 */}
            <div className="form-group">
              <label className="form-label">交易方向 *</label>
              <div style={{display:'flex', gap:8}}>
                {['buy','sell'].map(dir => (
                  <button key={dir} className="btn btn-ghost"
                    style={{
                      flex:1, justifyContent:'center',
                      background: form.direction === dir ? (dir === 'buy' ? 'var(--red-dim)' : 'var(--green-dim)') : '',
                      color: form.direction === dir ? DIRECTION_COLOR[dir] : '',
                      borderColor: form.direction === dir ? (dir === 'buy' ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)') : '',
                      fontWeight: form.direction === dir ? 600 : 400,
                    }}
                    onClick={() => setForm(f => ({...f, direction:dir}))}
                  >
                    {DIRECTION_LABEL[dir]}
                  </button>
                ))}
              </div>
            </div>

            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12}}>
              <div className="form-group">
                <label className="form-label">股數 *</label>
                <input className="input" type="number" min="1" placeholder="如：1000股"
                  value={form.shares} onChange={e => setForm(f => ({...f, shares:e.target.value}))} />
              </div>
              <div className="form-group">
                <label className="form-label">模擬進場價 *</label>
                <input className="input" type="number" step="0.01" placeholder="元/股"
                  value={form.entry_price} onChange={e => setForm(f => ({...f, entry_price:e.target.value}))} />
              </div>
              <div className="form-group">
                <label className="form-label">停損價（選填）</label>
                <input className="input" type="number" step="0.01" placeholder="觸及此價位顯示警示"
                  value={form.stop_loss} onChange={e => setForm(f => ({...f, stop_loss:e.target.value}))} />
              </div>
              <div className="form-group">
                <label className="form-label">停利價（選填）</label>
                <input className="input" type="number" step="0.01" placeholder="觸及此價位顯示通知"
                  value={form.take_profit} onChange={e => setForm(f => ({...f, take_profit:e.target.value}))} />
              </div>
            </div>

            {form.shares && form.entry_price && (
              <div style={{background:'var(--bg-base)', padding:'10px 14px', borderRadius:6, marginBottom:14, fontSize:13}}>
                <div style={{color:'var(--text-secondary)'}}>
                  模擬{form.direction === 'buy' ? '買進' : '做空'} {Number(form.shares).toLocaleString()} 股
                  × ${Number(form.entry_price).toLocaleString()} =&nbsp;
                  <strong style={{color:'var(--text-primary)'}}>
                    ${(Number(form.shares) * Number(form.entry_price)).toLocaleString('zh-TW', {maximumFractionDigits:0})}
                  </strong>
                </div>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">備註</label>
              <input className="input" placeholder="策略說明，如：突破前高順勢做多"
                value={form.note} onChange={e => setForm(f => ({...f, note:e.target.value}))} />
            </div>

            <div style={{display:'flex', gap:10, justifyContent:'flex-end', marginTop:8}}>
              <button className="btn btn-ghost" onClick={() => setShowModal(false)}>取消</button>
              <button className="btn btn-primary" onClick={handleCreate}>建立模擬單</button>
            </div>
          </div>
        </div>
      )}

      {/* 平倉 Modal */}
      {closeModal && (
        <div className="modal-overlay" onClick={() => setCloseModal(null)}>
          <div className="modal" style={{maxWidth:360}} onClick={e => e.stopPropagation()}>
            <h2>模擬平倉 — {closeModal.name}</h2>
            <div className="form-group" style={{marginBottom:20}}>
              <label className="form-label">平倉價格</label>
              <input className="input" type="number" step="0.01"
                value={closePrice} onChange={e => setClosePrice(e.target.value)}
                placeholder={`現價 $${closeModal.price || ''}`}
              />
              <div style={{fontSize:11, color:'var(--text-muted)', marginTop:4}}>
                留空或使用現價：${closeModal.price?.toLocaleString()}
              </div>
            </div>
            <div style={{display:'flex', gap:10, justifyContent:'flex-end'}}>
              <button className="btn btn-ghost" onClick={() => setCloseModal(null)}>取消</button>
              <button className="btn btn-primary" onClick={handleClose}>確認平倉</button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
    </div>
  );
}
