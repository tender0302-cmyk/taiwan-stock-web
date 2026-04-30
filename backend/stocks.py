# =============================================
#  股票 API — 完整修正版
#  修正：
#    ✅ 中文名稱對照表（修正 6442 光聖等錯誤）
#    ✅ T86 三大法人欄位：外資=row[4]，投信=row[10]，合計=row[18]
#    ✅ 單位：股 ÷ 1000 = 張
#    ✅ 快取判斷：total_seconds() + 日期判斷
#    ✅ 清除快取時同時清記憶體快取
#    ✅ 融資融券支援 data0/data1 和單一 data 兩種格式
#    ✅ 背景預熱快取
#    ✅ 串流逐批顯示
# =============================================

import json, time, datetime, warnings, threading
import urllib3, requests
import yfinance as yf
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from auth import get_current_user, _verify
from database import get_conn

warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

router      = APIRouter()
_bg_loading = False

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

# ── 中文名稱對照表（完整修正版）────────────────────────────────
STOCK_NAMES_TW = {
    # 半導體
    "2330":"台積電","2303":"聯電","2308":"台達電","2327":"國巨",
    "2379":"瑞昱","2395":"研華","2408":"南亞科","2454":"聯發科",
    "3034":"聯詠","3711":"日月光投控",
    # 電子零組件
    "2317":"鴻海","2345":"智邦","2352":"佳世達","2353":"宏碁",
    "2357":"華碩","2376":"技嘉","2382":"廣達","2474":"可成",
    "3008":"大立光","4938":"和碩",
    # 金融
    "2801":"彰銀","2820":"華票","2880":"華南金","2881":"富邦金",
    "2882":"國泰金","2883":"開發金","2884":"玉山金","2885":"元大金",
    "2886":"兆豐金","2887":"台新金","2890":"永豐金","2891":"中信金",
    "5871":"中租-KY","5880":"合庫金",
    # 航運
    "2603":"長榮","2609":"陽明","2610":"華航","2615":"萬海","2618":"長榮航",
    # 鋼鐵
    "2002":"中鋼","2006":"東和鋼鐵","2014":"中鴻","2015":"豐興","2027":"大成鋼",
    # 塑化
    "1301":"台塑","1303":"南亞","1326":"台化","6505":"台塑化",
    # 水泥
    "1101":"台泥","1102":"亞泥",
    # 汽車
    "2201":"裕隆","2204":"中華汽車","2206":"三陽工業","2207":"和泰車","2227":"裕日車",
    # 食品
    "1216":"統一",
    # 紡織
    "1402":"遠東新","1434":"福懋",
    # 建材營造
    "2501":"國建","2504":"國產建材","2511":"太子建設","2515":"中工",
    "2520":"冠德","2524":"京城建設","2542":"興富發",
    # 電機機械
    "1590":"亞德客-KY","2049":"上銀","2059":"川湖",
    # 光電
    "3481":"群創","2409":"友達",
    # 網路通訊
    "2412":"中華電","3045":"台灣大哥大","4904":"遠傳",
    # 其他電子
    "2301":"光寶科","2360":"致茂","2362":"藍天電腦","2374":"佳能",
    "2385":"群光","2392":"正崴","2401":"凌陽","2404":"漢唐",
    "2406":"國碩","2415":"鉅祥","2417":"圓剛","2419":"仲琦",
    "2449":"京元電子","2450":"神腦","2451":"創見","2458":"義隆",
    "2461":"光群雷","2462":"寶碩","2464":"盛群","2465":"麗臺",
    "2466":"冠西電","2468":"凌華","2471":"資通電","2472":"立隆電",
    "2476":"鉅翔","2477":"美隆電","2480":"敦吉","2481":"強茂",
    "2482":"連展投控","2483":"百容","2485":"兆赫","2486":"一詮",
    "2488":"漢平","2489":"瑞軒","2491":"吉祥全","2492":"華景電",
    "2493":"揚博","2495":"普安","2496":"卓越","2497":"鑫永銓",
    # 個股修正（重要）
    "6442":"光聖",          # 修正：非嘉聯益
    "6191":"精成科技",
    "2436":"偉詮電",
    "5269":"祥碩",
    "2467":"志聖",
    "2354":"鴻準",
    "2409":"友達光電",
    # ETF
    "0050":"元大台灣50",
    "0051":"元大中型100",
    "00631L":"元大台灣50正2",
    "00632R":"元大台灣50反1",
    "00881":"國泰台灣5G+",
    "00878":"國泰永續高股息",
    "00900":"富邦特選高股息30",
    "00919":"群益台灣精選高息",
    "00929":"復華台灣科技優息",
    "00934":"中信成長高股息",
    "00940":"元大台灣價值高息",
    "00981A":"統一台灣動力",
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

CACHE_TTL = 3600

# ── 三大法人快取 ──────────────────────────────────────────────
_institutional_cache = {"data": {}, "date": ""}
_margin_cache        = {"data": {}, "date": ""}
_bg_loading          = False


def fetch_institutional_data() -> dict:
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
                    rows = data.get("data", [])
                    for row in rows:
                        try:
                            if len(row) < 18: continue
                            code = row[0].strip()
                            if not code or not code.isdigit(): continue
                            # T86 正確欄位（19欄格式，已驗證）：
                            # [4]  外陸資淨買超（不含外資自營）← 外資
                            # [10] 投信淨買超                 ← 投信
                            # [18] 三大法人合計
                            # 單位：股 ÷ 1000 = 張
                            result[code] = {
                                "foreign_net": round(pn(row[4])  / 1000),
                                "trust_net":   round(pn(row[10]) / 1000),
                                "total_net":   round(pn(row[18]) / 1000),
                            }
                        except: continue
                    _institutional_cache["data"] = result
                    _institutional_cache["date"] = today
                    break
        except: pass
        time.sleep(0.3)
    return result


def fetch_margin_data() -> dict:
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
                    if "data0" in data or "data1" in data:
                        for row in data.get("data0", []):
                            try:
                                if len(row) < 6: continue
                                code = str(row[0]).strip()
                                if code and code.isdigit(): margin_dict[code] = pn(row[5])
                            except: continue
                        for row in data.get("data1", []):
                            try:
                                if len(row) < 6: continue
                                code = str(row[0]).strip()
                                if code and code.isdigit(): short_dict[code] = pn(row[5])
                            except: continue
                    elif "data" in data:
                        rows = data.get("data", [])
                        if rows:
                            row_len = len(rows[0])
                            mi = 5
                            si = 13 if row_len >= 19 else (11 if row_len >= 16 else 10)
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
                        result[code] = {"margin_balance": m, "short_balance": s}
                    _margin_cache["data"] = result
                    _margin_cache["date"] = today
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
        # total_seconds() 而非 .seconds，同時加日期判斷
        if (now - updated).total_seconds() > CACHE_TTL or updated.date() != now.date():
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

        # 中文名稱優先
        cn_name = STOCK_NAMES_TW.get(code)
        en_name = info.get("longName") or info.get("shortName") or code

        # 法人資料
        inst   = fetch_institutional_data().get(code, {})
        margin = fetch_margin_data().get(code, {})

        result = {
            "code":           code,
            "ticker":         ticker,
            "name":           cn_name or en_name,
            "short_name":     cn_name or (info.get("shortName") or code),
            "sector":         SECTOR_MAP.get(code, "其他"),
            "price":          round(price, 2),
            "change_1d":      round(change_1d, 2),
            "change_5d":      round(change_5d, 2),
            "market_cap_b":   round(market_cap_b, 0),
            "ma5":            round(ma5, 2),
            "ma20":           round(ma20, 2),
            "ma60":           round(ma60, 2) if ma60 else None,
            "rsi":            round(rsi, 1),
            "k":              round(k_val, 1),
            "d":              round(d_val, 1),
            "macd":           round(macd_val, 3),
            "macd_signal":    round(sig_val, 3),
            "bb_pct":         round(bb_pct, 1),
            "vol_ratio":      round(vol_ratio, 2),
            "pe_ratio":       info.get("trailingPE"),
            "eps":            info.get("trailingEps"),
            "52w_high":       h52,
            "52w_low":        l52,
            "52w_pos":        pos52,
            "dividend_yield": info.get("dividendYield"),
            "revenue_growth": info.get("revenueGrowth"),
            "foreign_net":    inst.get("foreign_net", 0),
            "trust_net":      inst.get("trust_net",   0),
            "inst_total":     inst.get("total_net",   0),
            "margin_balance": margin.get("margin_balance", 0),
            "short_balance":  margin.get("short_balance",  0),
        }
        _set_cache(code, result)
        return result
    except Exception as e:
        return None


def _warmup_cache():
    global _bg_loading
    _bg_loading = True
    print("🔄 背景快取預熱開始...")
    count = 0
    for code in STATIC_WATCHLIST:
        try:
            fetch_one_stock(code)
            count += 1
            time.sleep(0.2)
        except Exception:
            pass
    _bg_loading = False
    print(f"✅ 背景快取預熱完成，共 {count} 檔")


def start_warmup():
    t = threading.Thread(target=_warmup_cache, daemon=True)
    t.start()


# ── Routes ────────────────────────────────────────────────────

@router.get("/list")
def get_stock_list(user: dict = Depends(get_current_user)):
    results = []
    missing  = []
    for code in STATIC_WATCHLIST:
        cached = _get_cached(code)
        if cached: results.append(cached)
        else: missing.append(code)
    for code in missing:
        data = fetch_one_stock(code)
        if data: results.append(data)
        time.sleep(0.05)
    order = {c: i for i, c in enumerate(STATIC_WATCHLIST)}
    results.sort(key=lambda s: order.get(s["code"], 999))
    return {
        "stocks":     results,
        "total":      len(results),
        "is_loading": _bg_loading,
        "cache_status": f"快取 {len(results)-len(missing)} 檔 / 即時 {len(missing)} 檔",
    }


@router.get("/search/{code}")
def search_stock(code: str, user: dict = Depends(get_current_user)):
    """手動輸入代碼查詢單一股票（不限觀察清單）。"""
    code = code.strip().upper()
    data = fetch_one_stock(code)
    if not data:
        raise HTTPException(status_code=404, detail=f"找不到股票 {code}，請確認代碼是否正確")
    return data


@router.get("/{code}")
def get_single_stock(code: str, user: dict = Depends(get_current_user)):
    data = fetch_one_stock(code)
    if not data:
        raise HTTPException(status_code=404, detail=f"找不到股票 {code}")
    return data


@router.get("/stream")
def get_stock_stream(token: str = ""):
    try:
        _verify(token)
    except Exception:
        from fastapi.responses import Response
        return Response(status_code=401)

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


@router.delete("/cache")
def clear_cache(user: dict = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM stock_cache")
    conn.commit()
    conn.close()
    _institutional_cache["data"] = {}
    _institutional_cache["date"] = ""
    _margin_cache["data"] = {}
    _margin_cache["date"] = ""
    return {"message": "所有快取已清除，下次載入將抓取最新資料"}
