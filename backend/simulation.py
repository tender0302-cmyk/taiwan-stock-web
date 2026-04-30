# =============================================
#  模擬下單 API
#  功能：
#    - 建立模擬倉位（買進/賣出）
#    - 追蹤模擬損益（與真實持倉完全分開）
#    - 設定停損停利點
#    - 模擬倉位歷史記錄
# =============================================

import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_current_user
from database import get_conn
from stocks import fetch_one_stock, STOCK_NAMES_TW

router = APIRouter()

class SimOrderCreate(BaseModel):
    code:        str
    direction:   str    # "buy" 或 "sell"
    shares:      float  # 股數
    entry_price: float  # 模擬進場價
    stop_loss:   float | None = None   # 停損價
    take_profit: float | None = None   # 停利價
    note:        str = ""

class SimOrderUpdate(BaseModel):
    stop_loss:   float | None = None
    take_profit: float | None = None
    note:        str   | None = None


def init_sim_table():
    """建立模擬倉位資料表（首次使用時）。"""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sim_orders (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            code         TEXT    NOT NULL,
            name         TEXT    NOT NULL,
            direction    TEXT    NOT NULL DEFAULT 'buy',
            shares       REAL    NOT NULL,
            entry_price  REAL    NOT NULL,
            stop_loss    REAL,
            take_profit  REAL,
            status       TEXT    NOT NULL DEFAULT 'open',
            close_price  REAL,
            close_date   TEXT,
            note         TEXT    DEFAULT '',
            created_at   TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


# ── Routes ────────────────────────────────────────────────────

@router.get("/")
def list_sim_orders(user: dict = Depends(get_current_user), status: str = "open"):
    """
    取得模擬倉位清單。
    status: 'open'（持倉中）| 'closed'（已平倉）| 'all'（全部）
    """
    init_sim_table()
    conn = get_conn()
    if status == "all":
        rows = conn.execute(
            "SELECT * FROM sim_orders WHERE user_id=? ORDER BY created_at DESC",
            (user["sub"],)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM sim_orders WHERE user_id=? AND status=? ORDER BY created_at DESC",
            (user["sub"], status)
        ).fetchall()
    conn.close()

    results = []
    for row in rows:
        h = dict(row)

        # 計算持有天數
        try:
            created = datetime.datetime.fromisoformat(h["created_at"])
            h["hold_days"] = (datetime.datetime.now() - created).days
        except Exception:
            h["hold_days"] = 0

        shares      = float(h["shares"])
        entry_price = float(h["entry_price"])
        direction   = h.get("direction", "buy")

        if h["status"] == "open":
            # 抓即時股價計算浮動損益
            stock = fetch_one_stock(h["code"])
            if stock:
                current_price = float(stock["price"])
                if direction == "buy":
                    pnl_pct    = (current_price - entry_price) / entry_price * 100
                    pnl_amount = (current_price - entry_price) * shares
                else:  # sell（做空）
                    pnl_pct    = (entry_price - current_price) / entry_price * 100
                    pnl_amount = (entry_price - current_price) * shares

                h["current_price"] = current_price
                h["pnl_pct"]       = round(pnl_pct, 2)
                h["pnl_amount"]    = round(pnl_amount, 0)
                h["market_value"]  = round(current_price * shares, 0)
                h["change_1d"]     = stock.get("change_1d", 0)

                # 停損停利觸發判斷
                h["stop_loss_triggered"]   = False
                h["take_profit_triggered"] = False
                if h.get("stop_loss"):
                    if direction == "buy" and current_price <= h["stop_loss"]:
                        h["stop_loss_triggered"] = True
                    elif direction == "sell" and current_price >= h["stop_loss"]:
                        h["stop_loss_triggered"] = True
                if h.get("take_profit"):
                    if direction == "buy" and current_price >= h["take_profit"]:
                        h["take_profit_triggered"] = True
                    elif direction == "sell" and current_price <= h["take_profit"]:
                        h["take_profit_triggered"] = True
            else:
                h["current_price"] = None
                h["pnl_pct"]       = None
                h["pnl_amount"]    = None
                h["market_value"]  = round(entry_price * shares, 0)
                h["change_1d"]     = None
                h["stop_loss_triggered"]   = False
                h["take_profit_triggered"] = False

        else:
            # 已平倉：用平倉價計算實現損益
            close_price = float(h.get("close_price") or entry_price)
            if direction == "buy":
                pnl_pct    = (close_price - entry_price) / entry_price * 100
                pnl_amount = (close_price - entry_price) * shares
            else:
                pnl_pct    = (entry_price - close_price) / entry_price * 100
                pnl_amount = (entry_price - close_price) * shares
            h["current_price"] = close_price
            h["pnl_pct"]       = round(pnl_pct, 2)
            h["pnl_amount"]    = round(pnl_amount, 0)
            h["market_value"]  = round(close_price * shares, 0)
            h["change_1d"]     = None
            h["stop_loss_triggered"]   = False
            h["take_profit_triggered"] = False

        h["entry_value"] = round(entry_price * shares, 0)  # 進場總金額
        results.append(h)

    return results


@router.post("/")
def create_sim_order(req: SimOrderCreate, user: dict = Depends(get_current_user)):
    """建立模擬下單。"""
    init_sim_table()

    if req.direction not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="direction 必須為 buy 或 sell")
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="股數必須大於 0")
    if req.entry_price <= 0:
        raise HTTPException(status_code=400, detail="進場價必須大於 0")

    cn_name = STOCK_NAMES_TW.get(req.code)
    if not cn_name:
        stock   = fetch_one_stock(req.code)
        cn_name = (stock.get("short_name") or stock.get("name") if stock else None) or req.code
    name = cn_name

    conn = get_conn()
    cursor = conn.execute(
        """INSERT INTO sim_orders
           (user_id, code, name, direction, shares, entry_price, stop_loss, take_profit, note)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (user["sub"], req.code, name, req.direction,
         req.shares, req.entry_price, req.stop_loss, req.take_profit, req.note)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    direction_label = "買進" if req.direction == "buy" else "做空"
    total = req.entry_price * req.shares
    return {
        "id":      new_id,
        "message": f"模擬{direction_label} {name}({req.code}) {req.shares:,.0f}股 @ ${req.entry_price:,.2f}，總金額 ${total:,.0f}"
    }


@router.put("/{order_id}")
def update_sim_order(order_id: int, req: SimOrderUpdate, user: dict = Depends(get_current_user)):
    """修改模擬倉位的停損停利設定。"""
    init_sim_table()
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM sim_orders WHERE id=? AND user_id=? AND status='open'",
        (order_id, user["sub"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="找不到持倉中的模擬單")
    updates = {k: v for k, v in req.dict().items() if v is not None}
    if updates:
        conn.execute(
            f"UPDATE sim_orders SET {', '.join(f'{k}=?' for k in updates)} WHERE id=?",
            (*updates.values(), order_id)
        )
        conn.commit()
    conn.close()
    return {"message": "停損停利已更新"}


@router.post("/{order_id}/close")
def close_sim_order(order_id: int, close_price: float, user: dict = Depends(get_current_user)):
    """
    模擬平倉。
    close_price：平倉價格（可手動輸入，或用現價）
    """
    init_sim_table()
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM sim_orders WHERE id=? AND user_id=? AND status='open'",
        (order_id, user["sub"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="找不到持倉中的模擬單")

    conn.execute(
        "UPDATE sim_orders SET status='closed', close_price=?, close_date=datetime('now') WHERE id=?",
        (close_price, order_id)
    )
    conn.commit()
    conn.close()

    direction  = row["direction"]
    shares     = float(row["shares"])
    entry      = float(row["entry_price"])
    pnl        = (close_price - entry) * shares if direction == "buy" else (entry - close_price) * shares
    pnl_pct    = (close_price - entry) / entry * 100 if direction == "buy" else (entry - close_price) / entry * 100

    return {
        "message":    f"模擬平倉完成",
        "pnl_amount": round(pnl, 0),
        "pnl_pct":    round(pnl_pct, 2),
    }


@router.delete("/{order_id}")
def delete_sim_order(order_id: int, user: dict = Depends(get_current_user)):
    """刪除模擬單記錄。"""
    init_sim_table()
    conn = get_conn()
    conn.execute("DELETE FROM sim_orders WHERE id=? AND user_id=?", (order_id, user["sub"]))
    conn.commit()
    conn.close()
    return {"message": "已刪除"}
