import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { portfolioAPI, analysisAPI, stocksAPI } from '../api';


// 中文股票名稱對照表（前端也備份一份，避免 API 回傳英文）
const STOCK_NAMES_TW = {
  "2330":"台積電","2317":"鴻海","2454":"聯發科","2308":"台達電",
  "2412":"中華電","3008":"大立光","2382":"廣達","2603":"長榮",
  "6505":"台塑化","2881":"富邦金","2882":"國泰金","2886":"兆豐金",
  "2884":"玉山金","3711":"日月光投控","2357":"華碩","2303":"聯電",
  "2002":"中鋼","1303":"南亞","1301":"台塑","2409":"友達",
  "2327":"國巨","2345":"智邦","2376":"技嘉","2395":"研華",
  "2379":"瑞昱","2408":"南亞科","3034":"聯詠","3045":"台灣大",
  "4938":"和碩","2891":"中信金","2885":"元大金","2883":"開發金",
  "2880":"華南金","2890":"永豐金","5880":"合庫金","5871":"中租-KY",
  "2887":"台新金","2801":"彰銀","1216":"統一","1402":"遠東新",
  "2501":"國建","2504":"國產","1590":"亞德客-KY","2049":"上銀",
  "2059":"川湖","2201":"裕隆","2204":"中華","2207":"和泰車",
  "2227":"裕日車","1101":"台泥","1102":"亞泥","2609":"陽明",
  "2615":"萬海","2610":"華航","2618":"長榮航","2002":"中鋼",
  "2352":"佳世達","2353":"宏碁","2301":"光寶科","2474":"可成",
  "1326":"台化","2360":"致茂","0050":"元大台灣50","0051":"元大中型100",
  "6442":"嘉聯益","6191":"精成科","2436":"偉詮電","2354":"鴻準",
  "5269":"祥碩","2467":"志聖","2317":"鴻海",
};

export default function PortfolioPage() {
  const [holdings,  setHoldings]  = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [report,    setReport]    = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editItem,  setEditItem]  = useState(null);
  const [toast,     setToast]     = useState(null);
  const [form, setForm] = useState({ code: '', shares: '', cost: '', buy_date: '', note: '', _name: '' });
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

  // 自動帶入股票中文名稱
  async function handleCodeBlur() {
    const code = form.code.trim();
    if (!code || code.length < 2) return;
    // 優先用前端對照表（中文）
    const cnName = STOCK_NAMES_TW[code];
    if (cnName) {
      setForm(f => ({ ...f, _name: cnName }));
      return;
    }
    // 找不到再問 API
    try {
      const res = await stocksAPI.getOne(code);
      const name = STOCK_NAMES_TW[code] || res.data.short_name || res.data.name || code;
      setForm(f => ({ ...f, _name: name }));
    } catch (e) {
      setForm(f => ({ ...f, _name: STOCK_NAMES_TW[code] || '' }));
    }
  }

  async function handleSave() {
    if (!form.code.trim() || !form.shares || !form.cost || !form.buy_date) {
      showToast('請填入所有必要欄位', 'error');
      return;
    }
    const sharesNum = parseFloat(form.shares);
    const costNum   = parseFloat(form.cost);
    if (isNaN(sharesNum) || sharesNum <= 0) { showToast('股數必須大於 0', 'error'); return; }
    if (isNaN(costNum)   || costNum   <= 0) { showToast('成本價必須大於 0', 'error'); return; }

    try {
      if (editItem) {
        await portfolioAPI.update(editItem.id, {
          shares:   sharesNum,
          cost:     costNum,
          buy_date: form.buy_date,
          note:     form.note,
        });
        showToast('更新成功');
      } else {
        await portfolioAPI.add({
          code:     form.code.trim(),
          shares:   sharesNum,
          cost:     costNum,
          buy_date: form.buy_date,
          note:     form.note,
        });
        const displayName = STOCK_NAMES_TW[form.code.trim()] || form._name || form.code;
        showToast(`已新增 ${displayName} ${sharesNum.toLocaleString()} 股`);
      }
      setShowModal(false);
      setEditItem(null);
      setForm({ code: '', shares: '', cost: '', buy_date: '', note: '', _name: '' });
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
    } catch (e) { showToast('刪除失敗', 'error'); }
  }

  function openEdit(h) {
    setEditItem(h);
    setForm({ code: h.code, shares: String(h.shares), cost: String(h.cost), buy_date: h.buy_date, note: h.note || '', _name: h.name });
    setShowModal(true);
  }

  function openAdd() {
    setEditItem(null);
    setForm({ code: '', shares: '', cost: '', buy_date: '', note: '', _name: '' });
    setShowModal(true);
  }

  async function runPortfolioAnalysis() {
    if (!holdings.length) return;
    setAnalyzing(true); setReport(null);
    try {
      const res = await analysisAPI.analyzePortfolio(holdings);
      setReport(res.data.report);
    } catch (e) { showToast('AI 分析失敗', 'error'); }
    finally { setAnalyzing(false); }
  }

  // 統計
  const totalCost  = holdings.reduce((s, h) => s + (h.cost_total || 0), 0);
  const totalValue = holdings.reduce((s, h) => s + (h.value_now  || 0), 0);
  const totalPnl   = totalValue - totalCost;
  const totalPct   = totalCost > 0 ? totalPnl / totalCost * 100 : 0;

  // 損益顯示顏色（台股：漲=紅，跌=綠）
  const pnlColor = (val) => (val || 0) >= 0 ? 'var(--red)' : 'var(--green)';

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo"><h1>📈 台股 AI</h1><span>分析平台</span></div>
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
            <div className="page-subtitle">支援整股與零股｜管理持有股票，取得 AI 健康檢查報告</div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn btn-ghost" onClick={runPortfolioAnalysis} disabled={analyzing || !holdings.length}>
              {analyzing ? <><span className="spinner" style={{ width: 13, height: 13 }}/> 分析中...</> : '🤖 AI 持倉分析'}
            </button>
            <button className="btn btn-primary" onClick={openAdd}>+ 新增持倉</button>
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
            <div className="stat-value" style={{ color: pnlColor(totalPnl) }}>
              {totalPct >= 0 ? '+' : ''}{totalPct.toFixed(2)}%
            </div>
            <div className="stat-sub" style={{ color: pnlColor(totalPnl) }}>
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
            <div className="report-container"><ReactMarkdown>{report}</ReactMarkdown></div>
          </div>
        )}

        {/* 持倉表格 */}
        {loading ? (
          <div className="loading"><div className="spinner"/><span>載入中...</span></div>
        ) : holdings.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>
            還沒有持倉記錄，點擊「新增持倉」開始追蹤（支援整股與零股）
          </div>
        ) : (
          <div className="card" style={{ padding: 0 }}>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>股票</th>
                    <th style={{ textAlign: 'right' }}>持股數</th>
                    <th style={{ textAlign: 'right' }}>成本價</th>
                    <th style={{ textAlign: 'right' }}>現價</th>
                    <th style={{ textAlign: 'right' }}>損益</th>
                    <th style={{ textAlign: 'right' }}>今日</th>
                    <th style={{ textAlign: 'right' }}>總成本</th>
                    <th style={{ textAlign: 'right' }}>市值</th>
                    <th style={{ textAlign: 'right' }}>持有天數</th>
                    <th>買入日</th>
                    <th>備註</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map(h => {
                    const pct = h.pnl_pct || 0;
                    const c1d = h.change_1d || 0;
                    return (
                      <tr key={h.id}>
                        <td>
                          <div className="td-name">{STOCK_NAMES_TW[h.code] || h.name}</div>
                          <div className="td-code">{h.code}</div>
                        </td>
                        {/* 持股數（支援零股顯示） */}
                        <td className="td-number" style={{ textAlign: 'right' }}>
                          {Number(h.shares) % 1 === 0
                            ? Number(h.shares).toLocaleString()
                            : Number(h.shares).toLocaleString(undefined, { maximumFractionDigits: 2 })
                          } 股
                        </td>
                        <td className="td-number" style={{ textAlign: 'right' }}>${Number(h.cost).toLocaleString()}</td>
                        <td className="td-price" style={{ textAlign: 'right' }}>
                          {h.current_price != null ? `$${Number(h.current_price).toLocaleString()}` : '-'}
                        </td>
                        {/* 損益 */}
                        <td style={{ textAlign: 'right' }}>
                          <div className="td-number" style={{ color: pnlColor(pct) }}>
                            {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                          </div>
                          {h.pnl_amt != null && (
                            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: pnlColor(h.pnl_amt) }}>
                              {h.pnl_amt >= 0 ? '+' : ''}{Number(h.pnl_amt).toLocaleString('zh-TW', { maximumFractionDigits: 0 })}
                            </div>
                          )}
                        </td>
                        {/* 今日漲跌 */}
                        <td className="td-number" style={{ textAlign: 'right', color: c1d >= 0 ? 'var(--red)' : 'var(--green)' }}>
                          {c1d != null ? `${c1d >= 0 ? '+' : ''}${c1d.toFixed(2)}%` : '-'}
                        </td>
                        {/* 總成本 */}
                        <td className="td-number" style={{ textAlign: 'right', fontSize: 12 }}>
                          ${Number(h.cost_total || 0).toLocaleString('zh-TW', { maximumFractionDigits: 0 })}
                        </td>
                        {/* 市值 */}
                        <td className="td-number" style={{ textAlign: 'right', fontSize: 12 }}>
                          {h.value_now != null ? `$${Number(h.value_now).toLocaleString('zh-TW', { maximumFractionDigits: 0 })}` : '-'}
                        </td>
                        <td className="td-number" style={{ textAlign: 'right' }}>{h.hold_days} 天</td>
                        <td className="td-number" style={{ fontSize: 12 }}>{h.buy_date}</td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 100 }}>{h.note || '-'}</td>
                        <td>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button className="btn btn-ghost"  style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => openEdit(h)}>編輯</button>
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
            <h2>{editItem ? `編輯持倉 — ${editItem.name}` : '新增持倉'}</h2>

            {/* 股票代碼（編輯時不可改） */}
            <div className="form-group">
              <label className="form-label">股票代碼 *</label>
              <input
                className="input"
                placeholder="例如：2330、6442"
                value={form.code}
                onChange={e => setForm(f => ({ ...f, code: e.target.value, _name: '' }))}
                onBlur={handleCodeBlur}
                disabled={!!editItem}
              />
              {form._name && (
                <div style={{ fontSize: 12, color: 'var(--accent)', marginTop: 4 }}>
                  ✓ {form._name}
                </div>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {/* 持股數 — 支援小數（零股） */}
              <div className="form-group">
                <label className="form-label">股數 * <span style={{fontSize:11,color:"var(--text-muted)"}}>（整股如1000，零股如100）</span></label>
                <input
                  className="input"
                  type="number"
                  min="0.01"
                  step="1"
                  placeholder="整張輸入1000、2000，零股輸入100、500"
                  value={form.shares}
                  onChange={e => setForm(f => ({ ...f, shares: e.target.value }))}
                />
                {form.shares && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
                    {Number(form.shares) % 1000 === 0 && Number(form.shares) >= 1000
                      ? `= ${Number(form.shares) / 1000} 張（${Number(form.shares).toLocaleString()} 股）`
                      : `零股 ${Number(form.shares).toLocaleString()} 股`}
                  </div>
                )}
              </div>
              {/* 成本價 */}
              <div className="form-group">
                <label className="form-label">買入成本（每股）*</label>
                <input
                  className="input"
                  type="number"
                  step="0.01"
                  placeholder="元"
                  value={form.cost}
                  onChange={e => setForm(f => ({ ...f, cost: e.target.value }))}
                />
                {form.shares && form.cost && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
                    預估總成本：${(Number(form.shares) * Number(form.cost)).toLocaleString('zh-TW', { maximumFractionDigits: 0 })}
                    （{Number(form.shares).toLocaleString()} 股 × ${Number(form.cost).toLocaleString()} /股）
                  </div>
                )}
              </div>
            </div>

            {/* 買入日期 */}
            <div className="form-group">
              <label className="form-label">買入日期 *</label>
              <input
                className="input"
                type="date"
                value={form.buy_date}
                onChange={e => setForm(f => ({ ...f, buy_date: e.target.value }))}
              />
            </div>

            {/* 備註 */}
            <div className="form-group">
              <label className="form-label">備註</label>
              <input
                className="input"
                placeholder="選填，例如：長線布局、零股定期定額"
                value={form.note}
                onChange={e => setForm(f => ({ ...f, note: e.target.value }))}
              />
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
