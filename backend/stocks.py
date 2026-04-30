# =============================================
#  股票 API — 完整重寫版
#  架構改變：
#    背景排程定時抓取 → 存入資料庫
#    API 只讀資料庫 → 毫秒回應
#    解決 Railway 30秒超時問題
# =============================================

import json, time, datetime, warnings, threading
import urllib3, requests
import yfinance as yf
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from database import get_conn

warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

router = APIRouter()

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

# ── 中文名稱對照表 ────────────────────────────────────────────
STOCK_NAMES_TW = {
    "2330":"台積電","2303":"聯電","2308":"台達電","2327":"國巨",
    "2379":"瑞昱","2395":"研華","2408":"南亞科","2454":"聯發科",
    "3034":"聯詠","3711":"日月光投控","2317":"鴻海","2345":"智邦",
    "2352":"佳世達","2353":"宏碁","2357":"華碩","2376":"技嘉",
    "2382":"廣達","2474":"可成","3008":"大立光","4938":"和碩",
    "2801":"彰銀","2820":"華票","2880":"華南金","2881":"富邦金",
    "2882":"國泰金","2883":"開發金","2884":"玉山金","2885":"元大金",
    "2886":"兆豐金","2887":"台新金","2890":"永豐金","2891":"中信金",
    "5871":"中租-KY","5880":"合庫金","2603":"長榮","2609":"陽明",
    "2610":"華航","2615":"萬海","2618":"長榮航","2002":"中鋼",
    "2006":"東和鋼鐵","2014":"中鴻","2015":"豐興","2027":"大成鋼",
    "1301":"台塑","1303":"南亞","1326":"台化","6505":"台塑化",
    "1101":"台泥","1102":"亞泥","2201":"裕隆","2204":"中華汽車",
    "2206":"三陽工業","2207":"和泰車","2227":"裕日車","1216":"統一",
    "1402":"遠東新","1434":"福懋","2501":"國建","2504":"國產建材",
    "2511":"太子建設","2515":"中工","2520":"冠德","2524":"京城建設",
    "2542":"興富發","1590":"亞德客-KY","2049":"上銀","2059":"川湖",
    "3481":"群創","2409":"友達","2412":"中華電","3045":"台灣大哥大",
    "4904":"遠傳","2301":"光寶科","2360":"致茂","2362":"藍天電腦",
    "2374":"佳能","2385":"群光","2392":"正崴","2401":"凌陽",
    "2404":"漢唐","2406":"國碩","2415":"鉅祥","2417":"圓剛",
    "2419":"仲琦","2449":"京元電子","2450":"神腦","2451":"創見",
    "2458":"義隆","2461":"光群雷","2462":"寶碩","2464":"盛群",
    "2465":"麗臺","2466":"冠西電","2468":"凌華","2471":"資通電",
    "2472":"立隆電","2476":"鉅翔","2477":"美隆電","2480":"敦吉",
    "2481":"強茂","2482":"連展投控","2483":"百容","2485":"兆赫",
    "2486":"一詮","2488":"漢平","2489":"瑞軒","2491":"吉祥全",
    "2492":"華景電","2493":"揚博","2495":"普安","2496":"卓越",
    "2497":"鑫永銓","6442":"光聖","6191":"精成科技","2436":"偉詮電",
    "5269":"祥碩","2467":"志聖","2354":"鴻準","0050":"元大台灣50",
    "0051":"元大中型100","00631L":"元大台灣50正2","00981A":"統一台灣動力",
}

SECTOR_MAP = {
    "2330":"半導體","2303":"半導體","2308":"半導體","2454":"半導體",
    "3711":"半導體","2379":"半導體","2408":"半導體","2395":"半導體",
    "3034":"半導體","2327":"半導體","2317":"電子零組件","2382":"電子零組件",
    "2357":"電子零組件","2376":"電子零組件","2345":"電子零組件",
    "2301":"電子零組件","2353":"電子零組件","3008":"電子零組件",
    "2474":"電子零組件","4938":"電子零組件","2352":"電子零組件",
    "2412":"網路通訊","3045":"網路通訊","4904":"網路通訊",
    "2881":"金融保險","2882":"金融保險","2884":"金融保險","2886":"金融保險",
    "2891":"金融保險","2885":"金融保險","2883":"金融保險","2880":"金融保險",
    "2890":"金融保險","5880":"金融保險","5871":"金融保險","2887":"金融保險",
    "2801":"金融保險","2820":"金融保險","2603":"航運","2609":"航運",
    "2615":"航運","2610":"航運","2618":"航運","2002":"鋼鐵","2006":"鋼鐵",
    "2014":"鋼鐵","2015":"鋼鐵","2027":"鋼鐵","1303":"塑化","1326":"塑化",
    "6505":"塑化","1101":"水泥","1102":"水泥","1301":"水泥","2207":"汽車",
    "2201":"汽車","2204":"汽車","2206":"汽車","2227":"汽車","1216":"食品",
    "1402":"紡織","1434":"紡織","2501":"建材營造","2504":"建材營造",
    "2511":"建材營造","2515":"建材營造","1590":"電機機械","2049":"電機機械",
    "2059":"電機機械","2409":"光電","3481":"光電",
}

STATIC_WATCHLIST = [
    "2330","2317","2454","2308","2881","2882","2412","3008","2303","2002",
    "1303","1301","2886","1326","2884","2891","3711","2357","2382","2603",
    "2207","2395","4938","2376","2327","2345","3045","2408","6505","5880",
    "2801","2885","2883","2880","2890","5871","2887","1216","2379","3034",
    "2353","2301","1402","2474","2049","2618","1101","1102","1590","2006",
    "2014","2015","2027","2059","2201","2204","2206","2227","2231","2352",
    "2360","2362","2374","2385","2392","2401","2404","2406","2409","2415",
    "2417","2419","2449","2450","2451","2458","2460","2461","2462","2464",
    "2465","2466","2468","2471","2472","2475","2476","2477","2480","2481",
    "2482","2483","2485","2486","2488","2489","2491","2492","2493","2495",
    "2496","2497","2501","2504","2506","2511","2514","2515","2516","2520",
]

# ── 三大法人快取（記憶體）────────────────────────────────────
_inst_cache   = {"data": {}, "date": ""}
_bg_status    = {"running": False, "done": 0, "total": len(STATIC_WATCHLIST)}


# ── 資料庫操作 ───────────────────────────────────────────────

def _init_stock_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_data (
            code       TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def _save_stock(code: str, data: dict):
    _init_stock_table()
    conn = get_conn()
    now  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT OR REPLACE INTO stock_data (code, data, updated_at) VALUES (?,?,?)",
        (code, json.dumps(data, ensure_ascii=False), now)
    )
    conn.commit()
    conn.close()

def _load_stock(code: str) -> dict | None:
    _init_stock_table()
    conn = get_conn()
    row  = conn.execute("SELECT data, updated_at FROM stock_data WHERE code=?", (code,)).fetchone()
    conn.close()
    if not row: return None
    try:
        updated = datetime.datetime.strptime(row["updated_at"], "%Y-%m-%d %H:%M:%S")
        now     = datetime.datetime.now()
        # 超過1小時或不是今天 → 過期
        if (now - updated).total_seconds() > 3600 or updated.date() != now.date():
            return None
    except Exception:
        return None
    return json.loads(row["data"])

def _load_all_stocks() -> list[dict]:
    """從資料庫讀取所有今日有效股票資料。"""
    _init_stock_table()
    conn = get_conn()
    today = datetime.date.today().strftime("%Y-%m-%d")
    rows  = conn.execute(
        "SELECT data FROM stock_data WHERE updated_at >= ?",
        (today + " 00:00:00",)
    ).fetchall()
    conn.close()
    results = []
    for row in rows:
        try:
            results.append(json.loads(row["data"]))
        except Exception:
            pass
    return results


# ── 三大法人資料 ─────────────────────────────────────────────

def fetch_institutional_data() -> dict:
    today = datetime.date.today().strftime("%Y%m%d")
    if _inst_cache["date"] == today and _inst_cache["data"]:
        return _inst_cache["data"]
    result = {}
    for days_back in range(1, 6):
        d = datetime.date.today() - datetime.timedelta(days=days_back)
        if d.weekday() >= 5: continue
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
                            if len(row) < 18: continue
                            code = row[0].strip()
                            if not code or not code.isdigit(): continue
                            result[code] = {
                                "foreign_net": round(pn(row[4])  / 1000),
                                "trust_net":   round(pn(row[10]) / 1000),
                                "total_net":   round(pn(row[18]) / 1000),
                            }
                        except: continue
                    _inst_cache["data"] = result
                    _inst_cache["date"] = today
                    break
        except: pass
        time.sleep(0.3)
    return result


# ── 單支股票抓取 ─────────────────────────────────────────────

def _fetch_stock_data(code: str) -> dict | None:
    """抓單支股票資料，自動嘗試 .TW 和 .TWO。"""
    ticker = None
    hist   = None

    for suffix in [".TW", ".TWO"]:
        try:
            t = yf.Ticker(f"{code}{suffix}")
            h = t.history(period="60d")
            if not h.empty and len(h) >= 5:
                ticker = f"{code}{suffix}"
                hist   = h
                break
        except Exception:
            continue

    if not ticker or hist is None:
        return None

    try:
        stock = yf.Ticker(ticker)
        info  = stock.info or {}
    except Exception:
        info = {}

    try:
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

        mkt = ((info.get("marketCap") or 0) / 1e8)
        h52 = info.get("fiftyTwoWeekHigh")
        l52 = info.get("fiftyTwoWeekLow")
        pos52 = round((price - l52) / (h52 - l52) * 100, 1) if (h52 and l52 and h52 != l52) else None

        cn = STOCK_NAMES_TW.get(code)
        en = info.get("longName") or info.get("shortName") or code

        inst = fetch_institutional_data().get(code, {})

        return {
            "code":          code,
            "ticker":        ticker,
            "name":          cn or en,
            "short_name":    cn or (info.get("shortName") or code),
            "sector":        SECTOR_MAP.get(code, "其他"),
            "price":         round(price, 2),
            "change_1d":     round(change_1d, 2),
            "change_5d":     round(change_5d, 2),
            "market_cap_b":  round(mkt, 0),
            "ma5":           round(ma5, 2),
            "ma20":          round(ma20, 2),
            "ma60":          round(ma60, 2) if ma60 else None,
            "rsi":           round(rsi, 1),
            "k":             round(k_val, 1),
            "d":             round(d_val, 1),
            "macd":          round(macd_val, 3),
            "macd_signal":   round(sig_val, 3),
            "bb_pct":        round(bb_pct, 1),
            "vol_ratio":     round(vol_ratio, 2),
            "pe_ratio":      info.get("trailingPE"),
            "eps":           info.get("trailingEps"),
            "52w_high":      h52,
            "52w_low":       l52,
            "52w_pos":       pos52,
            "dividend_yield":info.get("dividendYield"),
            "revenue_growth":info.get("revenueGrowth"),
            "foreign_net":   inst.get("foreign_net", 0),
            "trust_net":     inst.get("trust_net", 0),
            "inst_total":    inst.get("total_net", 0),
        }
    except Exception as e:
        return None


# ── 背景批次抓取排程 ─────────────────────────────────────────

def _bg_fetch_all():
    """
    背景執行：逐一抓取所有股票存入資料庫。
    每次啟動時執行，之後每小時執行一次。
    """
    if _bg_status["running"]:
        return
    _bg_status["running"] = True
    _bg_status["done"]    = 0
    _bg_status["total"]   = len(STATIC_WATCHLIST)

    print(f"🔄 背景抓取開始：{len(STATIC_WATCHLIST)} 檔")
    for code in STATIC_WATCHLIST:
        try:
            # 先檢查資料庫是否已有今日資料
            existing = _load_stock(code)
            if existing:
                _bg_status["done"] += 1
                continue
            data = _fetch_stock_data(code)
            if data:
                _save_stock(code, data)
            _bg_status["done"] += 1
            time.sleep(0.5)  # 避免 Yahoo Finance 限速
        except Exception as e:
            _bg_status["done"] += 1
            continue

    _bg_status["running"] = False
    print(f"✅ 背景抓取完成：{_bg_status['done']} 檔")

    # 每小時重新抓一次（更新收盤後資料）
    def _schedule_next():
        time.sleep(3600)
        _bg_fetch_all()
    threading.Thread(target=_schedule_next, daemon=True).start()


def start_warmup():
    """應用程式啟動時觸發背景抓取。"""
    threading.Thread(target=_bg_fetch_all, daemon=True).start()


# ── API Routes ───────────────────────────────────────────────

@router.get("/list")
def get_stock_list(user: dict = Depends(get_current_user)):
    """
    從資料庫讀取股票資料（毫秒回應）。
    背景排程負責更新資料庫，API 只讀不寫。
    """
    results = _load_all_stocks()
    # 依觀察清單順序排序
    order = {c: i for i, c in enumerate(STATIC_WATCHLIST)}
    results.sort(key=lambda s: order.get(s.get("code",""), 999))

    return {
        "stocks":     results,
        "total":      len(results),
        "is_loading": _bg_status["running"],
        "bg_progress": f"{_bg_status['done']}/{_bg_status['total']}",
        "cache_status": f"資料庫 {len(results)} 檔" + (
            f"（背景載入中 {_bg_status['done']}/{_bg_status['total']}）"
            if _bg_status["running"] else ""
        ),
    }


@router.get("/status")
def get_load_status(user: dict = Depends(get_current_user)):
    """查詢背景載入進度。"""
    db_count = len(_load_all_stocks())
    return {
        "db_count":   db_count,
        "is_loading": _bg_status["running"],
        "done":       _bg_status["done"],
        "total":      _bg_status["total"],
        "pct":        round(_bg_status["done"] / max(_bg_status["total"], 1) * 100),
    }


@router.post("/refresh")
def trigger_refresh(user: dict = Depends(get_current_user)):
    """手動觸發重新抓取所有股票。"""
    if _bg_status["running"]:
        return {"message": "背景抓取已在執行中"}
    # 清空資料庫舊資料
    conn = get_conn()
    conn.execute("DELETE FROM stock_data")
    conn.commit()
    conn.close()
    _inst_cache["data"] = {}
    _inst_cache["date"] = ""
    threading.Thread(target=_bg_fetch_all, daemon=True).start()
    return {"message": "已觸發重新抓取，請稍候 2-3 分鐘"}


@router.get("/search/{code}")
def search_stock(code: str, user: dict = Depends(get_current_user)):
    """手動輸入代碼查詢（不限觀察清單，支援 .TW / .TWO）。"""
    code = code.strip()
    # 先查資料庫
    cached = _load_stock(code)
    if cached: return cached
    # 即時抓取
    data = _fetch_stock_data(code)
    if not data:
        raise HTTPException(status_code=404, detail=f"找不到股票 {code}，請確認代碼是否正確")
    _save_stock(code, data)
    return data


@router.get("/{code}")
def get_single_stock(code: str, user: dict = Depends(get_current_user)):
    cached = _load_stock(code)
    if cached: return cached
    data = _fetch_stock_data(code)
    if not data:
        raise HTTPException(status_code=404, detail=f"找不到股票 {code}")
    _save_stock(code, data)
    return data


@router.delete("/cache")
def clear_cache(user: dict = Depends(get_current_user)):
    """清除資料庫快取並重新抓取。"""
    conn = get_conn()
    conn.execute("DELETE FROM stock_data")
    conn.commit()
    conn.close()
    _inst_cache["data"] = {}
    _inst_cache["date"] = ""
    threading.Thread(target=_bg_fetch_all, daemon=True).start()
    return {"message": "快取已清除，背景重新抓取中（約 2-3 分鐘）"}


# 向後相容別名（供 portfolio.py、simulation.py 使用）
def fetch_one_stock(code: str) -> dict | None:
    return _load_stock(code) or _fetch_stock_data(code)
