# =============================================
#  資料庫設定 (SQLite)
# =============================================

import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "taiwan_stock.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # 使用者白名單
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT  DEFAULT (datetime('now'))
        )
    """)

    # 持倉資料
    c.execute("""
        CREATE TABLE IF NOT EXISTS holdings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            code       TEXT    NOT NULL,
            name       TEXT    NOT NULL,
            shares     INTEGER NOT NULL,
            cost       REAL    NOT NULL,
            buy_date   TEXT    NOT NULL,
            note       TEXT    DEFAULT '',
            created_at TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 股價快取（減少 API 呼叫）
    c.execute("""
        CREATE TABLE IF NOT EXISTS stock_cache (
            code       TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # 建立預設管理員帳號（首次啟動時）
    from auth import hash_password
    try:
        c.execute(
            "INSERT INTO users (username, password, is_admin) VALUES (?, ?, 1)",
            ("admin", hash_password("changeme123"))
        )
        print("✅ 建立預設管理員帳號：admin / changeme123（請立即修改密碼）")
    except sqlite3.IntegrityError:
        pass  # 已存在

    conn.commit()
    conn.close()
    print("✅ 資料庫初始化完成")
