# =============================================
#  持倉 API — CRUD 操作
# =============================================

import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_current_user
from database import get_conn
from stocks import fetch_one_stock

router = APIRouter()

class HoldingCreate(BaseModel):
    code:     str
    shares:   int
    cost:     float
    buy_date: str
    note:     str = ""

class HoldingUpdate(BaseModel):
    shares:   int | None   = None
    cost:     float | None = None
    buy_date: str | None   = None
    note:     str | None   = None

# ── Routes ────────────────────────────────────────────────────

@router.get("/")
def list_holdings(user: dict = Depends(get_current_user)):
    """取得使用者所有持倉，含即時損益計算。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM holdings WHERE user_id=? ORDER BY buy_date DESC",
        (user["sub"],)
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        h = dict(row)

        # 計算持有天數
        try:
            buy_dt    = datetime.datetime.strptime(h["buy_date"], "%Y-%m-%d")
            h["hold_days"] = (datetime.datetime.now() - buy_dt).days
        except Exception:
            h["hold_days"] = 0

        # 抓即時股價
        stock = fetch_one_stock(h["code"])
        if stock:
            price       = stock["price"]
            shares_unit = h["shares"] * 1000
            cost_total  = h["cost"] * shares_unit
            value_now   = price * shares_unit
            h["current_price"] = price
            h["cost_total"]    = round(cost_total, 0)
            h["value_now"]     = round(value_now, 0)
            h["pnl_amt"]       = round(value_now - cost_total, 0)
            h["pnl_pct"]       = round((price - h["cost"]) / h["cost"] * 100, 2)
            h["change_1d"]     = stock.get("change_1d", 0)
            h["sector"]        = stock.get("sector", "其他")
        else:
            h["current_price"] = None
            h["cost_total"]    = round(h["cost"] * h["shares"] * 1000, 0)
            h["value_now"]     = None
            h["pnl_amt"]       = None
            h["pnl_pct"]       = None
            h["change_1d"]     = None
            h["sector"]        = "其他"

        results.append(h)

    return results

@router.post("/")
def add_holding(req: HoldingCreate, user: dict = Depends(get_current_user)):
    """新增持倉。"""
    # 自動查詢股票名稱
    stock = fetch_one_stock(req.code)
    name  = stock["short_name"] if stock else req.code

    conn = get_conn()
    cursor = conn.execute(
        """INSERT INTO holdings (user_id, code, name, shares, cost, buy_date, note)
           VALUES (?,?,?,?,?,?,?)""",
        (user["sub"], req.code, name, req.shares, req.cost, req.buy_date, req.note)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"id": new_id, "message": f"已新增 {name}({req.code}) {req.shares}張"}

@router.put("/{holding_id}")
def update_holding(holding_id: int, req: HoldingUpdate, user: dict = Depends(get_current_user)):
    """修改持倉資訊。"""
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM holdings WHERE id=? AND user_id=?",
        (holding_id, user["sub"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="找不到持倉記錄")

    updates = {k: v for k, v in req.dict().items() if v is not None}
    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(
            f"UPDATE holdings SET {set_clause} WHERE id=?",
            (*updates.values(), holding_id)
        )
        conn.commit()
    conn.close()
    return {"message": "更新成功"}

@router.delete("/{holding_id}")
def delete_holding(holding_id: int, user: dict = Depends(get_current_user)):
    """刪除持倉記錄。"""
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM holdings WHERE id=? AND user_id=?",
        (holding_id, user["sub"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="找不到持倉記錄")
    conn.execute("DELETE FROM holdings WHERE id=?", (holding_id,))
    conn.commit()
    conn.close()
    return {"message": "刪除成功"}
