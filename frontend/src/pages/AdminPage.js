import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authAPI } from '../api';

export default function AdminPage() {
  const [users,     setUsers]     = useState([]);
  const [showAdd,   setShowAdd]   = useState(false);
  const [showPwd,   setShowPwd]   = useState(false);
  const [form,      setForm]      = useState({ username: '', password: '' });
  const [pwdForm,   setPwdForm]   = useState({ old_password: '', new_password: '', confirm: '' });
  const [toast,     setToast]     = useState(null);
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const navigate = useNavigate();

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  async function loadUsers() {
    try {
      const res = await authAPI.listUsers();
      setUsers(res.data);
    } catch (e) { showToast('載入失敗', 'error'); }
  }

  useEffect(() => { loadUsers(); }, []);

  async function handleAddUser() {
    if (!form.username || !form.password) return showToast('請填入帳號和密碼', 'error');
    try {
      await authAPI.createUser(form.username, form.password);
      showToast(`帳號 ${form.username} 建立成功`);
      setShowAdd(false);
      setForm({ username: '', password: '' });
      loadUsers();
    } catch (e) { showToast(e.response?.data?.detail || '建立失敗', 'error'); }
  }

  async function handleDeleteUser(id, name) {
    if (!window.confirm(`確認刪除帳號 ${name}？`)) return;
    try {
      await authAPI.deleteUser(id);
      showToast(`已刪除 ${name}`);
      loadUsers();
    } catch (e) { showToast(e.response?.data?.detail || '刪除失敗', 'error'); }
  }

  async function handleChangePwd() {
    if (pwdForm.new_password !== pwdForm.confirm) return showToast('新密碼不一致', 'error');
    if (pwdForm.new_password.length < 6) return showToast('密碼至少 6 個字元', 'error');
    try {
      await authAPI.changePassword(pwdForm.old_password, pwdForm.new_password);
      showToast('密碼修改成功，請重新登入');
      setTimeout(() => { localStorage.clear(); navigate('/login'); }, 1500);
    } catch (e) { showToast(e.response?.data?.detail || '修改失敗', 'error'); }
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>📈 台股 AI</h1>
          <span>分析平台</span>
        </div>
        <Link className="nav-item" to="/">股票看板</Link>
        <Link className="nav-item" to="/portfolio">持倉管理</Link>
        <Link className="nav-item active" to="/admin">帳號管理</Link>
        <div style={{ marginTop: 'auto', borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div className="nav-item" onClick={() => { localStorage.clear(); navigate('/login'); }} style={{ color: 'var(--red)' }}>登出</div>
        </div>
      </aside>

      <main className="main-content">
        <div className="page-header">
          <div>
            <div className="page-title">帳號管理</div>
            <div className="page-subtitle">管理平台白名單帳號（最多 4 個使用者）</div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn btn-ghost" onClick={() => setShowPwd(true)}>修改我的密碼</button>
            <button className="btn btn-primary" onClick={() => setShowAdd(true)} disabled={users.length >= 4}>
              + 新增帳號
            </button>
          </div>
        </div>

        {/* 使用者列表 */}
        <div className="card" style={{ padding: 0 }}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>帳號</th>
                  <th>身份</th>
                  <th>建立時間</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id}>
                    <td className="td-code">{u.id}</td>
                    <td className="td-name">{u.username}</td>
                    <td>
                      {u.is_admin
                        ? <span className="badge" style={{ background: 'var(--amber-dim)', color: 'var(--amber)', border: '1px solid rgba(245,158,11,0.2)' }}>管理員</span>
                        : <span className="badge" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>一般使用者</span>
                      }
                    </td>
                    <td className="td-number" style={{ fontSize: 12 }}>{u.created_at}</td>
                    <td>
                      {u.username !== user.username && (
                        <button className="btn btn-danger" style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => handleDeleteUser(u.id, u.username)}>
                          刪除
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div style={{ marginTop: 16, fontSize: 12, color: 'var(--text-muted)' }}>
          ℹ️ 目前 {users.length}/4 個帳號。新帳號建立後請告知對方在登入後修改密碼。
        </div>
      </main>

      {/* 新增帳號 Modal */}
      {showAdd && (
        <div className="modal-overlay" onClick={() => setShowAdd(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>新增帳號</h2>
            <div className="form-group">
              <label className="form-label">帳號</label>
              <input className="input" placeholder="設定帳號" value={form.username} onChange={e => setForm(f => ({...f, username: e.target.value}))} />
            </div>
            <div className="form-group" style={{ marginBottom: 20 }}>
              <label className="form-label">初始密碼</label>
              <input className="input" type="password" placeholder="至少 6 個字元" value={form.password} onChange={e => setForm(f => ({...f, password: e.target.value}))} />
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setShowAdd(false)}>取消</button>
              <button className="btn btn-primary" onClick={handleAddUser}>建立</button>
            </div>
          </div>
        </div>
      )}

      {/* 修改密碼 Modal */}
      {showPwd && (
        <div className="modal-overlay" onClick={() => setShowPwd(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>修改密碼</h2>
            <div className="form-group">
              <label className="form-label">目前密碼</label>
              <input className="input" type="password" value={pwdForm.old_password} onChange={e => setPwdForm(f => ({...f, old_password: e.target.value}))} />
            </div>
            <div className="form-group">
              <label className="form-label">新密碼</label>
              <input className="input" type="password" value={pwdForm.new_password} onChange={e => setPwdForm(f => ({...f, new_password: e.target.value}))} />
            </div>
            <div className="form-group" style={{ marginBottom: 20 }}>
              <label className="form-label">確認新密碼</label>
              <input className="input" type="password" value={pwdForm.confirm} onChange={e => setPwdForm(f => ({...f, confirm: e.target.value}))} />
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setShowPwd(false)}>取消</button>
              <button className="btn btn-primary" onClick={handleChangePwd}>修改</button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
    </div>
  );
}
