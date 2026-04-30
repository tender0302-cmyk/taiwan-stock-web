# =============================================
#  持倉 API — CRUD 操作
#
#  ★ 計算邏輯（方案C）完全清楚版 ★
#
#  使用者輸入「股數」（不是張數）：
#    整張 1 張 → 輸入 1000
#    整張 2 張 → 輸入 2000
#    零股 100股 → 輸入 100
#
#  所有金額計算：
#    總成本   = 每股成本價 × 股數
#    現在市值 = 當前股價   × 股數
#    損益金額 = 現在市值 - 總成本
#    損益%    = (當前股價 - 每股成本價) / 每股成本價 × 100
#
#  範例：
#    光寶科 1000股，成本$173，現價$172
#    總成本   = 173 × 1000 = 173,000
#    現在市值 = 172 × 1000 = 172,000
#    損益金額 = 172,000 - 173,000 = -1,000
#    損益%    = (172 - 173) / 173 × 100 = -0.58%
# =============================================

import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_current_user
from database import get_conn
from stocks import fetch_one_stock, STOCK_NAMES_TW

router = APIRouter()

class HoldingCreate(BaseModel):
    code:     str
    shares:   float   # 直接輸入股數
    cost:     float   # 每股成本價（元）
    buy_date: str
    note:     str = ""

class HoldingUpdate(BaseModel):
    shares:   float | None = None
    cost:     float | None = None
    buy_date: str   | None = None
    note:     str   | None = None


@router.get("/")
def list_holdings(user: dict = Depends(get_current_user)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM holdings WHERE user_id=? ORDER BY buy_date DESC",
        (user["sub"],)
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        h = dict(row)

        # 持有天數
        try:
            buy_dt = datetime.datetime.strptime(h["buy_date"], "%Y-%m-%d")
            h["hold_days"] = (datetime.datetime.now() - buy_dt).days
        except Exception:
            h["hold_days"] = 0

        shares         = float(h["shares"])        # 股數（直接使用）
        cost_per_share = float(h["cost"])           # 每股成本價

        stock = fetch_one_stock(h["code"])
        if stock:
            price        = float(stock["price"])
            total_cost   = cost_per_share * shares   # 總成本
            market_value = price * shares            # 現在市值
            pnl_amount   = market_value - total_cost # 損益金額
            pnl_pct      = (price - cost_per_share) / cost_per_share * 100 if cost_per_share > 0 else 0

            h["current_price"] = price
            h["cost_total"]    = round(total_cost, 0)
            h["value_now"]     = round(market_value, 0)
            h["pnl_amt"]       = round(pnl_amount, 0)
            h["pnl_pct"]       = round(pnl_pct, 2)
            h["change_1d"]     = stock.get("change_1d", 0)
            h["sector"]        = stock.get("sector", "其他")
        else:
            h["current_price"] = None
            h["cost_total"]    = round(cost_per_share * shares, 0)
            h["value_now"]     = None
            h["pnl_amt"]       = None
            h["pnl_pct"]       = None
            h["change_1d"]     = None
            h["sector"]        = "其他"

        results.append(h)

    return results


@router.post("/")
def add_holding(req: HoldingCreate, user: dict = Depends(get_current_user)):
    cn_name = STOCK_NAMES_TW.get(req.code)
    if not cn_name:
        stock   = fetch_one_stock(req.code)
        cn_name = (stock.get("short_name") or stock.get("name") if stock else None) or req.code
    name = cn_name

    conn = get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO holdings (user_id, code, name, shares, cost, buy_date, note) VALUES (?,?,?,?,?,?,?)",
            (user["sub"], req.code, name, req.shares, req.cost, req.buy_date, req.note)
        )
        conn.commit()
        new_id = cursor.lastrowid
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()

    total = req.cost * req.shares
    return {"id": new_id, "message": f"已新增 {name} {req.shares:,.0f}股，總成本 ${total:,.0f}"}


@router.put("/{holding_id}")
def update_holding(holding_id: int, req: HoldingUpdate, user: dict = Depends(get_current_user)):
    conn = get_conn()
    row  = conn.execute("SELECT * FROM holdings WHERE id=? AND user_id=?", (holding_id, user["sub"])).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="找不到持倉記錄")
    updates = {k: v for k, v in req.dict().items() if v is not None}
    if updates:
        conn.execute(f"UPDATE holdings SET {', '.join(f'{k}=?' for k in updates)} WHERE id=?", (*updates.values(), holding_id))
        conn.commit()
    conn.close()
    return {"message": "更新成功"}


@router.delete("/{holding_id}")
def delete_holding(holding_id: int, user: dict = Depends(get_current_user)):
    conn = get_conn()
    row  = conn.execute("SELECT * FROM holdings WHERE id=? AND user_id=?", (holding_id, user["sub"])).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="找不到持倉記錄")
    conn.execute("DELETE FROM holdings WHERE id=?", (holding_id,))
    conn.commit()
    conn.close()
    return {"message": "刪除成功"}
