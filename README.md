# 台股 AI 分析平台 — 部署指南

## 📁 專案結構

```
taiwan_stock_web/
├── backend/               ← Python FastAPI 後端
│   ├── main.py            主程式
│   ├── auth.py            認證模組（JWT）
│   ├── stocks.py          股票資料 API
│   ├── portfolio.py       持倉 CRUD API
│   ├── analysis.py        AI 分析 API
│   ├── database.py        SQLite 資料庫
│   ├── requirements.txt   Python 套件
│   └── render.yaml        Render 部署設定
│
└── frontend/              ← React 前端
    ├── src/
    │   ├── App.js         路由設定
    │   ├── App.css        全域樣式
    │   ├── api.js         API 請求
    │   ├── index.js       進入點
    │   └── pages/
    │       ├── LoginPage.js      登入頁
    │       ├── DashboardPage.js  股票看板（主頁）
    │       ├── PortfolioPage.js  持倉管理
    │       └── AdminPage.js      帳號管理
    ├── public/index.html
    ├── package.json
    └── vercel.json        Vercel 部署設定
```

---

## 🚀 部署步驟

### Step 1：部署後端到 Render

1. 把 `backend/` 資料夾上傳到 GitHub（建立一個新 repo）

2. 前往 [render.com](https://render.com) 註冊/登入

3. New → Web Service → 連接你的 GitHub repo

4. 設定：
   - **Name**: `taiwan-stock-api`
   - **Root Directory**: `backend`
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

5. 在 Environment Variables 填入：
   - `ANTHROPIC_API_KEY` → 你的 Claude API Key
   - `JWT_SECRET` → 隨便填一串長字串（建議32位以上）

6. 點 Deploy → 等待部署完成，記下後端網址（例如 `https://taiwan-stock-api.onrender.com`）

---

### Step 2：部署前端到 Vercel

1. 把 `frontend/` 資料夾上傳到 GitHub（可以同一個 repo 的子目錄）

2. 前往 [vercel.com](https://vercel.com) 註冊/登入

3. New Project → 連接 GitHub repo

4. 設定：
   - **Root Directory**: `frontend`
   - **Framework Preset**: Create React App

5. 在 Environment Variables 填入：
   - `REACT_APP_API_URL` → 你的 Render 後端網址（Step 1 記下的那個）

6. 點 Deploy → 等待完成，Vercel 會給你一個前端網址

---

### Step 3：首次登入與設定

1. 用瀏覽器打開 Vercel 給的前端網址

2. 使用預設帳號登入：
   - 帳號：`admin`
   - 密碼：`changeme123`

3. ⚠️ **立即修改密碼**：右上角 → 帳號管理 → 修改我的密碼

4. 新增其他使用者：帳號管理 → 新增帳號（最多 4 個）

---

## 💡 使用說明

### 股票看板
- 頁面載入時自動抓取台灣50 + 中型100 成分股資料
- 可依產業篩選，或用代碼/名稱搜尋
- **勾選 1-10 檔股票** → 點「AI 分析」→ 等 15-30 秒 → 取得進出場建議
- 點「更新資料」重新抓取；「清除快取」強制重抓

### 持倉管理
- 新增持倉：填入代碼（自動帶入名稱）、張數、成本價、買入日期
- 系統自動計算：持有天數、損益金額、損益百分比
- 點「AI 持倉分析」→ 取得每檔股票的持有/減碼/出場建議

### 帳號管理（管理員限定）
- 新增/刪除白名單帳號
- 修改自己的密碼

---

## ⚙️ 本機測試

```bash
# 後端
cd backend
pip install -r requirements.txt
ANTHROPIC_API_KEY=你的key JWT_SECRET=mysecret uvicorn main:app --reload

# 前端（另開終端機）
cd frontend
npm install
REACT_APP_API_URL=http://localhost:8000 npm start
```

---

## ⚠️ 注意事項

- Render 免費方案：服務 15 分鐘無請求會休眠，首次喚醒約需 30 秒
- 股票資料有 1 小時快取，不需要每次都重新抓取
- AI 分析只在你「按按鈕」時才呼叫 Claude，不會自動排程
- SQLite 存在 Render 的磁碟上；Render 免費方案每次部署會重置磁碟，建議升級到付費方案或改用 PostgreSQL

---

## 🔧 升級 PostgreSQL（可選）

若要持久化資料庫，在 Render 建立 PostgreSQL 服務後：

1. 安裝: `pip install psycopg2-binary`
2. 在 `database.py` 把 `sqlite3` 換成 `psycopg2`
3. 在 Render 環境變數設 `DATABASE_URL`
