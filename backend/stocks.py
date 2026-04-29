# =============================================
#  股票 API — 抓台灣50 + 中型100 資料
# =============================================

import json, time, datetime, warnings
import urllib3, requests, yfinance as yf, pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from database import get_conn

warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
router    = APIRouter()
_bg_loading = False   # 是否正在背景載入

# ── 背景預熱：啟動時自動抓所有股票存入快取 ──────────────────
import threading

def _warmup_cache():
    """背景執行，啟動時把所有股票預先快取好。"""
    global _bg_loading
    _bg_loading = True
    print("🔄 背景快取預熱開始...")
    count = 0
    for code in STATIC_WATCHLIST:
        try:
            fetch_one_stock(code)
            count += 1
            time.sleep(0.2)   # 降低對 Yahoo Finance 的壓力
        except Exception:
            pass
    _bg_loading = False
    print(f"✅ 背景快取預熱完成，共 {count} 檔")

def start_warmup():
    t = threading.Thread(target=_warmup_cache, daemon=True)
    t.start()

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

# ── 中文名稱對照表 ────────────────────────────────────────────
STOCK_NAMES_TW = {
    "2330":"台積電","2317":"鴻海","2454":"聯發科","2308":"台達電",
    "2412":"中華電","3008":"大立光","2382":"廣達","2603":"長榮",
    "6505":"台塑化","2881":"富邦金","2882":"國泰金","2886":"兆豐金",
    "2884":"玉山金","3711":"日月光投控","2357":"華碩","2303":"聯電",
    "2002":"中鋼","1303":"南亞","1301":"台塑","2409":"友達",
    "2327":"國巨","2345":"智邦","2376":"技嘉","2395":"研華",
    "2379":"瑞昱","2408":"南亞科","3034":"聯詠","3045":"台灣大",
    "4938":"和碩","2891":"中信金","2885":"元大金","2883":"開發金",
    "2880":"華南金","2890":"永豐金","5880":"合庫金","5871":"中租-KY",
    "2887":"台新金","2801":"彰銀","2820":"華票","1216":"統一",
    "1402":"遠東新","1434":"福懋","2501":"國建","2504":"國產",
    "2511":"太子","2515":"中工","1590":"亞德客-KY","2049":"上銀",
    "2059":"川湖","2201":"裕隆","2204":"中華","2206":"三陽工業",
    "2207":"和泰車","2227":"裕日車","1101":"台泥","1102":"亞泥",
    "2609":"陽明","2615":"萬海","2610":"華航","2618":"長榮航",
    "2006":"東和鋼鐵","2014":"中鴻","2015":"豐興","2027":"大成鋼",
    "3481":"群創","2352":"佳世達","2353":"宏碁","2301":"光寶科",
    "2474":"可成","1326":"台化","2360":"致茂","2362":"藍天",
    "2374":"佳能","2385":"群光","2392":"正崴","2401":"凌陽",
    "2404":"漢唐","2406":"國碩","2415":"鉅祥","2417":"圓剛",
    "2419":"仲琦","2449":"京元電子","2450":"神腦","2451":"創見",
    "2458":"義隆","2460":"建通","2461":"光群雷","2462":"寶碩",
    "2464":"盛群","2465":"麗臺","2466":"冠西電","2468":"凌華",
    "2471":"資通","2472":"立隆電","2475":"華映","2476":"鉅翔",
    "2477":"美隆電","2480":"敦吉","2481":"強茂","2482":"連展投控",
    "2483":"百容","2485":"兆赫","2486":"一詮","2488":"漢平",
    "2489":"瑞軒","2491":"吉祥全","2492":"華景電","2493":"揚博",
    "2495":"普安","2496":"卓越","2497":"鑫永銓","2506":"太設",
    "2514":"龍邦","2516":"新建","2520":"冠德","2524":"京城建設",
    "2527":"宏璟","2528":"皇普","2530":"華建","2534":"宏盛",
    "2536":"宏普","2537":"聯上發展","2538":"基泰","2542":"興富發",
}

# ── 三大法人快取 ──────────────────────────────────────────────
_institutional_cache = {"data": {}, "date": ""}
# ── 融資融券快取 ──────────────────────────────────────────────
_margin_cache = {"data": {}, "date": ""}

def fetch_margin_data() -> dict:
    """從 TWSE 抓融資融券，回傳 {code: {margin_balance, short_balance, margin_ratio}}"""
    import datetime, warnings, urllib3
    warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

    today = datetime.date.today().strftime("%Y%m%d")
    if _margin_cache["date"] == today and _margin_cache["data"]:
        return _margin_cache["data"]

    result = {}
    for days_back in range(1, 6):
        d = datetime.date.today() - datetime.timedelta(days=days_back)
        if d.weekday() >= 5:
            continue
        date_str = d.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&date={date_str}&selectType=ALL"
        try:
            r = requests.get(url, headers=HEADERS, timeout=12, verify=False)
            if r.status_code == 200 and r.text.strip():
                data = r.json()
                if data.get("stat") == "OK":
                    def pn(s):
                        try: return int(str(s).replace(",","").strip() or "0")
                        except: return 0

                    margin_dict = {}
                    short_dict  = {}

                    # 格式A：data0（融資）+ data1（融券）
                    if "data0" in data or "data1" in data:
                        for row in data.get("data0", []):
                            try:
                                if len(row) < 6: continue
                                code = str(row[0]).strip()
                                if code and code.isdigit():
                                    margin_dict[code] = pn(row[5])
                            except: continue
                        for row in data.get("data1", []):
                            try:
                                if len(row) < 6: continue
                                code = str(row[0]).strip()
                                if code and code.isdigit():
                                    short_dict[code] = pn(row[5])
                            except: continue

                    # 格式B：單一 data（融資融券合併）
                    elif "data" in data:
                        rows = data.get("data", [])
                        if rows:
                            row_len = len(rows[0]) if rows else 0
                            # 依欄位數判斷 index
                            if row_len >= 19:
                                mi, si = 5, 13
                            elif row_len >= 16:
                                mi, si = 5, 11
                            else:
                                mi, si = 5, 10
                            for row in rows:
                                try:
                                    code = str(row[0]).strip()
                                    if not code or not code.isdigit(): continue
                                    if len(row) > mi: margin_dict[code] = pn(row[mi])
                                    if len(row) > si: short_dict[code]  = pn(row[si])
                                except: continue

                    for code in set(list(margin_dict.keys()) + list(short_dict.keys())):
                        m = margin_dict.get(code, 0)
                        s = short_dict.get(code, 0)
                        ratio = round(m / s, 1) if s > 0 else None
                        result[code] = {
                            "margin_balance": m,
                            "short_balance":  s,
                            "margin_ratio":   ratio,
                        }
                    _margin_cache["data"] = result
                    _margin_cache["date"] = today
                    break
        except: pass
    return result

def fetch_institutional_data() -> dict:
    """從 TWSE 抓三大法人買賣超，回傳 {code: {foreign_net, trust_net, total_net}}"""
    import datetime, warnings, urllib3
    warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

    today = datetime.date.today().strftime("%Y%m%d")
    if _institutional_cache["date"] == today and _institutional_cache["data"]:
        return _institutional_cache["data"]

    result = {}
    for days_back in range(1, 6):
        d = datetime.date.today() - datetime.timedelta(days=days_back)
        if d.weekday() >= 5:
            continue
        date_str = d.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALL"
        try:
            r = requests.get(url, headers=HEADERS, timeout=12, verify=False)
            if r.status_code == 200 and r.text.strip():
                data = r.json()
                if data.get("stat") == "OK":
                    def pn(s):
                        try: return int(str(s).replace(",","").replace("+","").strip() or "0")
                        except: return 0
                    for row in data.get("data", []):
                        try:
                            if len(row) < 11: continue
                            code = row[0].strip()
                            result[code] = {
                                # TWSE T86 單位為「股」，÷1000 轉換為「張」
                                "foreign_net": round(pn(row[4])  / 1000),
                                "trust_net":   round(pn(row[7])  / 1000),
                                "dealer_net":  round(pn(row[10]) / 1000),
                                "total_net":   round(pn(row[-1]) / 1000),
                            }
                        except: continue
                    _institutional_cache["data"] = result
                    _institutional_cache["date"] = today
                    break
        except: pass
    return result


def _get_cached(code: str):
    conn = get_conn()
    row  = conn.execute("SELECT data, updated_at FROM stock_cache WHERE code=?", (code,)).fetchone()
    conn.close()
    if not row: return None
    try:
        updated = datetime.datetime.fromisoformat(row["updated_at"])
        now     = datetime.datetime.now()
        # 修正：用 total_seconds() 而非 seconds
        # 同時加入日期判斷：只要日期不同就視為過期，確保每天抓最新資料
        age_seconds = (now - updated).total_seconds()
        if age_seconds > CACHE_TTL or updated.date() != now.date():
            return None
    except Exception:
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

        # 優先用中文對照表
        cn_name = STOCK_NAMES_TW.get(code)
        en_name = info.get("longName") or info.get("shortName") or code

        # 法人資料
        inst_data   = fetch_institutional_data()
        inst        = inst_data.get(code, {})
        margin_data = fetch_margin_data()
        margin      = margin_data.get(code, {})

        result = {
            "code":         code,
            "ticker":       ticker,
            "name":         cn_name or en_name,
            "short_name":   cn_name or (info.get("shortName") or code),
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
            "foreign_net":  inst.get("foreign_net", 0),   # 外資淨買超（張）
            "trust_net":    inst.get("trust_net",   0),   # 投信淨買超（張）
            "inst_total":   inst.get("total_net",   0),   # 三大合計（張）
            "inst_date":    _institutional_cache.get("date", ""),  # 法人資料日期
            # 融資融券
            "margin_balance": margin.get("margin_balance", 0),
            "short_balance":  margin.get("short_balance",  0),
            "margin_ratio":   margin.get("margin_ratio",   None),
        }
        _set_cache(code, result)
        return result
    except Exception as e:
        return None

# ── Routes ────────────────────────────────────────────────────

@router.get("/list")
def get_stock_list(user: dict = Depends(get_current_user)):
    """
    回傳觀察清單。
    優先從快取讀取（快），快取不足時即時抓取（慢）。
    """
    results = []
    missing  = []

    # 先從快取讀（非常快）
    for code in STATIC_WATCHLIST:
        cached = _get_cached(code)
        if cached:
            results.append(cached)
        else:
            missing.append(code)

    # 若有缺漏（快取過期或首次），即時抓缺少的
    for code in missing:
        data = fetch_one_stock(code)
        if data:
            results.append(data)
        time.sleep(0.05)

    # 依 STATIC_WATCHLIST 順序排序
    order = {c: i for i, c in enumerate(STATIC_WATCHLIST)}
    results.sort(key=lambda s: order.get(s["code"], 999))

    return {
        "stocks":       results,
        "total":        len(results),
        "cache_status": f"快取 {len(results)-len(missing)} 檔 / 即時 {len(missing)} 檔",
        "is_loading":   _bg_loading,
    }

@router.get("/stream")
def get_stock_stream(token: str = ""):
    """串流回傳股票資料，token 透過 query string 傳遞（EventSource 限制）"""
    # 驗證 token
    from auth import _verify
    try:
        _verify(token)
    except Exception:
        from fastapi.responses import Response
        return Response(status_code=401)
    
    """
    串流回傳股票資料（Server-Sent Events）。
    前端可用 EventSource 接收，每抓到一檔就立刻顯示。
    """
    from fastapi.responses import StreamingResponse
    import json

    def generate():
        for code in STATIC_WATCHLIST:
            data = fetch_one_stock(code)
            if data:
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            time.sleep(0.05)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@router.get("/{code}")
def get_single_stock(code: str, user: dict = Depends(get_current_user)):
    """抓單一股票資料（用於持倉頁面）。"""
    data = fetch_one_stock(code)
    if not data:
        raise HTTPException(status_code=404, detail=f"找不到股票 {code}")
    return data

@router.delete("/cache")
def clear_cache(user: dict = Depends(get_current_user)):
    """清除股價快取（含法人快取），強制重新抓取。"""
    conn = get_conn()
    conn.execute("DELETE FROM stock_cache")
    conn.commit()
    conn.close()
    # 同時清除記憶體中的法人/融資快取
    _institutional_cache["data"] = {}
    _institutional_cache["date"] = ""
    _margin_cache["data"] = {}
    _margin_cache["date"] = ""
    return {"message": "所有快取已清除，下次載入將抓取最新資料"}
