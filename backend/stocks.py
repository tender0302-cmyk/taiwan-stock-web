# =============================================
#  股票 API — 抓台灣50 + 中型100 資料
# =============================================

import json, time, datetime, warnings
import urllib3, requests, yfinance as yf, pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from database import get_conn

warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
router = APIRouter()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

SECTOR_MAP = {
    "2330":"半導體","2303":"半導體","2308":"半導體","2454":"半導體","3711":"半導體",
    "2379":"半導體","2408":"半導體","2395":"半導體","3034":"半導體","2327":"半導體",
    "2317":"電子零組件","2382":"電子零組件","2357":"電子零組件","2376":"電子零組件",
    "2345":"電子零組件","2301":"電子零組件","2353":"電子零組件","3008":"電子零組件",
    "2474":"電子零組件","4938":"電子零組件","2352":"電子零組件",
    "2412":"網路通訊","3045":"網路通訊","4904":"網路通訊","2498":"網路通訊",
    "2881":"金融保險","2882":"金融保險","2884":"金融保險","2886":"金融保險",
    "2891":"金融保險","2885":"金融保險","2883":"金融保險","2880":"金融保險",
    "2890":"金融保險","5880":"金融保險","5871":"金融保險","2887":"金融保險",
    "2801":"金融保險","2820":"金融保險",
    "2603":"航運","2609":"航運","2615":"航運","2610":"航運","2618":"航運",
    "2002":"鋼鐵","2006":"鋼鐵","2014":"鋼鐵","2015":"鋼鐵","2027":"鋼鐵",
    "1303":"塑化","1326":"塑化","6505":"塑化",
    "1101":"水泥","1102":"水泥","1301":"水泥",
    "2207":"汽車","2201":"汽車","2204":"汽車","2206":"汽車","2227":"汽車",
    "1216":"食品","1402":"紡織","1434":"紡織",
    "2501":"建材營造","2504":"建材營造","2511":"建材營造","2515":"建材營造",
    "1590":"電機機械","2049":"電機機械","2059":"電機機械",
    "2409":"光電","3481":"光電",
}

STATIC_WATCHLIST = [
    "2330","2317","2454","2308","2881","2882","2412","3008","2303","2002","1303",
    "1301","2886","1326","2884","2891","3711","2357","2382","2603","2207","2395",
    "4938","2376","2327","2345","3045","2408","6505","5880","2801","2885","2883",
    "2880","2890","5871","2887","1216","2379","3034","2353","2301","1402","2474",
    "2049","2618","1101","1102","1590","2006","2014","2015","2027","2059","2201",
    "2204","2206","2227","2231","2352","2360","2362","2374","2385","2392","2401",
    "2404","2406","2409","2415","2417","2419","2449","2450","2451","2458","2460",
    "2461","2462","2464","2465","2466","2468","2471","2472","2475","2476","2477",
    "2480","2481","2482","2483","2485","2486","2488","2489","2491","2492","2493",
    "2495","2496","2497","2501","2504","2506","2511","2514","2515","2516","2520",
]

CACHE_TTL = 3600   # 1小時快取

def _get_cached(code: str):
    conn = get_conn()
    row  = conn.execute("SELECT data, updated_at FROM stock_cache WHERE code=?", (code,)).fetchone()
    conn.close()
    if not row: return None
    updated = datetime.datetime.fromisoformat(row["updated_at"])
    if (datetime.datetime.now() - updated).seconds > CACHE_TTL:
        return None
    return json.loads(row["data"])

def _set_cache(code: str, data: dict):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO stock_cache (code, data, updated_at) VALUES (?,?,datetime('now'))",
        (code, json.dumps(data, ensure_ascii=False))
    )
    conn.commit()
    conn.close()

def fetch_one_stock(code: str) -> dict | None:
    cached = _get_cached(code)
    if cached: return cached

    ticker = f"{code}.TW"
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="60d")
        if hist.empty or len(hist) < 5:
            return None

        info  = stock.info or {}
        close = hist["Close"]
        vol   = hist["Volume"]
        price = float(close.iloc[-1])

        ma5  = float(close.rolling(5).mean().iloc[-1])  if len(close) >= 5  else price
        ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else price
        ma60 = float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else None

        rsi = 50.0
        if len(close) >= 15:
            delta = close.diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean()
            rs    = gain / loss
            v     = (100 - 100 / (1 + rs)).iloc[-1]
            rsi   = float(v) if not pd.isna(v) else 50.0

        k_val = d_val = 50.0
        if len(close) >= 9:
            low9  = hist["Low"].rolling(9).min()
            high9 = hist["High"].rolling(9).max()
            denom = (high9 - low9).replace(0, float("nan"))
            rsv   = (close - low9) / denom * 100
            rsv   = rsv.fillna(50)
            k_s   = rsv.ewm(com=2).mean().iloc[-1]
            d_s   = rsv.ewm(com=2).mean().ewm(com=2).mean().iloc[-1]
            k_val = float(k_s) if not pd.isna(k_s) else 50.0
            d_val = float(d_s) if not pd.isna(d_s) else 50.0

        macd_val = sig_val = 0.0
        if len(close) >= 26:
            ema12    = close.ewm(span=12).mean()
            ema26    = close.ewm(span=26).mean()
            macd_val = float((ema12 - ema26).iloc[-1])
            sig_val  = float((ema12 - ema26).ewm(span=9).mean().iloc[-1])

        bb_pct = 50.0
        if len(close) >= 20:
            bb_mid = close.rolling(20).mean().iloc[-1]
            bb_std = close.rolling(20).std().iloc[-1]
            if bb_std and bb_std > 0:
                bb_u   = bb_mid + 2 * bb_std
                bb_l   = bb_mid - 2 * bb_std
                bb_pct = float((close.iloc[-1] - bb_l) / (bb_u - bb_l) * 100)
                bb_pct = max(0.0, min(100.0, bb_pct))

        vol_avg   = vol.rolling(min(20, len(vol))).mean().iloc[-1]
        vol_ratio = float(vol.iloc[-1] / vol_avg) if (vol_avg and vol_avg > 0) else 1.0
        change_1d = float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100) if len(close) >= 2 else 0.0
        change_5d = float((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100) if len(close) >= 6 else change_1d

        market_cap_b = ((info.get("marketCap") or 0) / 1e8)
        h52 = info.get("fiftyTwoWeekHigh")
        l52 = info.get("fiftyTwoWeekLow")
        pos52 = None
        if h52 and l52 and h52 != l52:
            pos52 = round((price - l52) / (h52 - l52) * 100, 1)

        result = {
            "code":         code,
            "ticker":       ticker,
            "name":         info.get("longName") or info.get("shortName") or code,
            "short_name":   info.get("shortName") or code,
            "sector":       SECTOR_MAP.get(code, "其他"),
            "price":        round(price, 2),
            "change_1d":    round(change_1d, 2),
            "change_5d":    round(change_5d, 2),
            "market_cap_b": round(market_cap_b, 0),
            "ma5":          round(ma5, 2),
            "ma20":         round(ma20, 2),
            "ma60":         round(ma60, 2) if ma60 else None,
            "rsi":          round(rsi, 1),
            "k":            round(k_val, 1),
            "d":            round(d_val, 1),
            "macd":         round(macd_val, 3),
            "macd_signal":  round(sig_val, 3),
            "bb_pct":       round(bb_pct, 1),
            "vol_ratio":    round(vol_ratio, 2),
            "pe_ratio":     info.get("trailingPE"),
            "eps":          info.get("trailingEps"),
            "52w_high":     h52,
            "52w_low":      l52,
            "52w_pos":      pos52,
            "dividend_yield": info.get("dividendYield"),
            "revenue_growth": info.get("revenueGrowth"),
        }
        _set_cache(code, result)
        return result
    except Exception as e:
        return None

# ── Routes ────────────────────────────────────────────────────

@router.get("/list")
def get_stock_list(user: dict = Depends(get_current_user)):
    """回傳觀察清單（台灣50+中型100），含快取機制。"""
    results = []
    for code in STATIC_WATCHLIST:
        data = fetch_one_stock(code)
        if data:
            results.append(data)
        time.sleep(0.1)
    return {"stocks": results, "total": len(results)}

@router.get("/{code}")
def get_single_stock(code: str, user: dict = Depends(get_current_user)):
    """抓單一股票資料（用於持倉頁面）。"""
    data = fetch_one_stock(code)
    if not data:
        raise HTTPException(status_code=404, detail=f"找不到股票 {code}")
    return data

@router.delete("/cache")
def clear_cache(user: dict = Depends(get_current_user)):
    """清除股價快取，強制重新抓取。"""
    conn = get_conn()
    conn.execute("DELETE FROM stock_cache")
    conn.commit()
    conn.close()
    return {"message": "快取已清除"}
