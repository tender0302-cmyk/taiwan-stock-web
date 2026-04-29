# =============================================
#  AI 分析 API — 按需呼叫 Claude
# =============================================

import os, datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import anthropic

from auth import get_current_user
from stocks import fetch_one_stock, SECTOR_MAP

router = APIRouter()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SECTOR_CHARACTERISTICS = {
    "半導體":   {"cycle": "科技循環", "lead_indicator": "費城半導體指數、AI資本支出", "peak_season": "Q3-Q4"},
    "電子零組件": {"cycle": "科技循環", "lead_indicator": "蘋果供應鏈、PC出貨量",    "peak_season": "Q3"},
    "網路通訊": {"cycle": "防禦型",   "lead_indicator": "5G建設進度",                "peak_season": "全年穩定"},
    "金融保險": {"cycle": "景氣循環", "lead_indicator": "升降息循環、房市熱度",       "peak_season": "Q1除息旺季"},
    "航運":     {"cycle": "景氣循環", "lead_indicator": "波羅的海指數、運費",         "peak_season": "Q3-Q4"},
    "鋼鐵":     {"cycle": "景氣循環", "lead_indicator": "中國鋼價、基建需求",         "peak_season": "Q2-Q3"},
    "塑化":     {"cycle": "景氣循環", "lead_indicator": "油價、中下游庫存",           "peak_season": "Q2"},
    "汽車":     {"cycle": "景氣循環", "lead_indicator": "EV滲透率",                   "peak_season": "Q4"},
    "食品":     {"cycle": "防禦型",   "lead_indicator": "糧食價格",                   "peak_season": "全年穩定"},
    "建材營造": {"cycle": "景氣循環", "lead_indicator": "房市交易量",                 "peak_season": "Q2-Q3"},
    "生技醫療": {"cycle": "成長型",   "lead_indicator": "FDA核准、臨床試驗",          "peak_season": "全年"},
}

STOP_LOSS_PCT = 7

# ── Request Models ────────────────────────────────────────────

class StockAnalysisRequest(BaseModel):
    codes: list[str]          # 勾選的股票代碼清單（最多10檔）

class PortfolioAnalysisRequest(BaseModel):
    holdings: list[dict]      # 持倉資料（含 pnl_pct、current_price 等）

# ── Helper ────────────────────────────────────────────────────

def format_stock_for_prompt(s: dict) -> str:
    def d(v): return f"+{v:,}" if v and v > 0 else (f"{v:,}" if v else "0")
    pe  = s.get("pe_ratio")
    rg  = s.get("revenue_growth")
    h52 = s.get("52w_high")
    l52 = s.get("52w_low")
    pos = s.get("52w_pos")
    char = SECTOR_CHARACTERISTICS.get(s.get("sector",""), {})
    return (
        f"\n{s.get('short_name',s['code'])}({s['code']}) 產業:{s.get('sector','其他')} 市值:{s.get('market_cap_b',0):.0f}億\n"
        f"  現價:${s['price']} 今日:{s.get('change_1d',0):+.1f}% 近5日:{s.get('change_5d',0):+.1f}% 52週位置:{pos or 'N/A'}%\n"
        f"  技術:RSI={s.get('rsi',50)} K={s.get('k',50)} D={s.get('d',50)} MACD={s.get('macd',0):.2f}/Sig={s.get('macd_signal',0):.2f} BB={s.get('bb_pct',50):.0f}% 量={s.get('vol_ratio',1):.1f}x\n"
        f"  均線:MA5={s.get('ma5',0)} MA20={s.get('ma20',0)} MA60={s.get('ma60','N/A')}\n"
        f"  基本:PE={pe or 'N/A'} 殖利率={'%.1f%%' % (s.get('dividend_yield',0)*100) if s.get('dividend_yield') else 'N/A'} 營收成長={'%.0f%%' % (rg*100) if rg else 'N/A'}\n"
        f"  產業屬性:{char.get('cycle','N/A')} 領先指標:{char.get('lead_indicator','N/A')} 旺季:{char.get('peak_season','N/A')}"
    )

# ── Routes ────────────────────────────────────────────────────

@router.post("/stocks")
def analyze_stocks(req: StockAnalysisRequest, user: dict = Depends(get_current_user)):
    """
    對勾選的股票進行 AI 分析。
    輸入：stock codes list（最多10檔）
    輸出：Markdown 格式的選股報告
    """
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="未設定 ANTHROPIC_API_KEY")
    if len(req.codes) > 10:
        raise HTTPException(status_code=400, detail="最多選擇 10 檔")
    if not req.codes:
        raise HTTPException(status_code=400, detail="請至少選擇 1 檔")

    # 抓股票資料
    stocks = []
    for code in req.codes:
        data = fetch_one_stock(code)
        if data:
            stocks.append(data)

    if not stocks:
        raise HTTPException(status_code=400, detail="無法取得股票資料")

    stocks_text = "".join(format_stock_for_prompt(s) for s in stocks)
    quarter     = f"Q{(datetime.datetime.now().month - 1) // 3 + 1}"
    today       = datetime.datetime.now().strftime("%Y-%m-%d")

    prompt = f"""你是台股資深基金經理人。今日({today} {quarter})，投資人勾選了以下{len(stocks)}檔股票請你分析：

{stocks_text}

風險偏好：最多持有10檔，單筆預算 $30,000，停損 {STOP_LOSS_PCT}%

請輸出完整的選股分析報告（繁體中文）：

## 📊 市場概況
（2-3句說明今日市場環境）

## 🔍 個股深度分析

對每一檔股票輸出：
### 【股票名稱 (代碼)】｜產業：XXX｜產業評分：⭐⭐⭐⭐（1-5顆）
- **進出場建議**：買進 / 觀望 / 賣出
- **建議進場價**：$XXX～$XXX（或「目前價位合理/偏高/偏低」）
- **目標價**：$XXX（潛在漲幅 +XX%）
- **停損價**：$XXX（-{STOP_LOSS_PCT}%）
- **建議張數**：X張（約$XX,XXX）
- **推薦分數**：XX/100
- **產業趨勢**：（1句說明產業目前狀況及是否適合布局）
- **技術面**：（KD/RSI/MACD/均線關鍵判斷）
- **籌碼面**：（如有資料則說明，否則略過）
- **基本面**：（EPS/本益比/成長性評價）
- **持有期間**：短線（1-2週）/ 中線（1-2月）/ 長線（3月+）
- **主要風險**：（1句）

## ⚠️ 整體風險提示
（技術面、產業面、總經面各1點）

## 📝 免責聲明
本報告由AI自動生成，僅供參考，不構成投資建議。"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg    = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    return {
        "report":   msg.content[0].text,
        "analyzed": [s["code"] for s in stocks],
        "count":    len(stocks)
    }


@router.post("/portfolio")
def analyze_portfolio(req: PortfolioAnalysisRequest, user: dict = Depends(get_current_user)):
    """
    對持倉進行健康檢查分析。
    """
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="未設定 ANTHROPIC_API_KEY")
    if not req.holdings:
        raise HTTPException(status_code=400, detail="沒有持倉資料")

    today = datetime.datetime.now().strftime("%Y-%m-%d")

    def holding_text(h: dict) -> str:
        pnl_emoji = "🟢" if (h.get("pnl_pct") or 0) >= 0 else "🔴"
        stock     = fetch_one_stock(h["code"])
        sl_price  = round(h["cost"] * (1 - STOP_LOSS_PCT / 100), 2)
        sl_gap    = round((h.get("current_price", h["cost"]) - sl_price) / h.get("current_price", h["cost"]) * 100, 1) if h.get("current_price") else 0
        warn      = " ⚠️ 接近停損線！" if sl_gap < 3 else ""

        tech = ""
        if stock:
            tech = (f"\n  技術:RSI={stock.get('rsi',50)} K={stock.get('k',50)} D={stock.get('d',50)} "
                    f"MACD={stock.get('macd',0):.2f} BB={stock.get('bb_pct',50):.0f}% MA20={stock.get('ma20',0)}")

        return (
            f"\n{pnl_emoji} {h['name']}({h['code']}) 持有{h['shares']}張{warn}\n"
            f"  成本:${h['cost']} 現價:${h.get('current_price','N/A')} "
            f"損益:{h.get('pnl_pct',0):+.2f}% / {h.get('pnl_amt',0):+,.0f}元\n"
            f"  停損線:${sl_price}（距離{sl_gap:.1f}%）持有:{h.get('hold_days',0)}天（{h['buy_date']}起）"
            f"{tech}"
        )

    holdings_text = "".join(holding_text(h) for h in req.holdings)

    total_cost  = sum((h.get("cost_total") or 0) for h in req.holdings)
    total_value = sum((h.get("value_now") or 0) for h in req.holdings)
    total_pnl   = total_value - total_cost
    total_pct   = total_pnl / total_cost * 100 if total_cost > 0 else 0

    prompt = f"""你是台股資深基金經理人，正在幫投資人做持倉健康檢查。

今日：{today}
整體持倉概況：總成本 ${total_cost:,.0f} / 目前市值 ${total_value:,.0f} / 整體損益 {total_pct:+.2f}%

持倉明細：
{holdings_text}

風險偏好：停損 {STOP_LOSS_PCT}%

請針對每一檔持股輸出持倉分析報告（繁體中文）：

## 💼 持倉健康檢查 — {today}

### 【股票名稱 (代碼)】｜損益：+X.X%
- **目前狀況**：現價/成本/損益金額/距停損線距離
- **技術面訊號**：（趨勢是否完好？支撐/壓力在哪？）
- **⚡ 操作建議**：**繼續持有** / **考慮減碼** / **建議出場**
- **建議理由**：（50字以內）
- **下一個觀察點**：（若繼續持有：目標價或觀察條件）
- **出場參考**：（若需出場：建議出場價位）

## 📊 持倉總覽
- 總投入：$X,XXX,XXX ｜ 目前市值：$X,XXX,XXX ｜ 整體損益：+X.X%
- 最強持股：XXX（+X.X%）｜ 最弱持股：XXX（-X.X%）

## 🎯 今日重點提醒
（最多3點，針對整體持倉的風險或機會）

## 📝 免責聲明
本報告由AI自動生成，僅供參考，不構成投資建議。"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg    = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=3500,
        messages=[{"role": "user", "content": prompt}]
    )
    return {
        "report":  msg.content[0].text,
        "summary": {
            "total_cost":  total_cost,
            "total_value": total_value,
            "total_pnl":   total_pnl,
            "total_pct":   round(total_pct, 2),
        }
    }
