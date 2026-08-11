#!/usr/bin/env python3
"""
股息投資組合追蹤 — FMP (Financial Modeling Prep) 版
Render 環境變數：FMP_API_KEY
"""

from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
import time
import requests
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__)

FMP_KEY = os.environ.get("FMP_API_KEY", "").strip()
FMP_BASE = "https://financialmodelingprep.com/api/v3"


def fmp_get(path: str, params: dict = None):
    if not FMP_KEY:
        return {"error": "尚未設定 FMP_API_KEY"}
    params = dict(params or {})
    params["apikey"] = FMP_KEY
    try:
        r = requests.get(f"{FMP_BASE}/{path}", params=params, timeout=25)
        data = r.json()
        if r.status_code != 200:
            if isinstance(data, dict):
                return {"error": data.get("Error Message") or data.get("error") or f"HTTP {r.status_code}"}
            return {"error": f"HTTP {r.status_code}"}
        if isinstance(data, dict) and data.get("Error Message"):
            return {"error": data["Error Message"]}
        return data
    except Exception as e:
        return {"error": str(e)}


def _f(v):
    if v is None or v == "" or v == "None":
        return None
    try:
        x = float(v)
        if x != x:  # NaN
            return None
        return x
    except (TypeError, ValueError):
        return None


def _date(v):
    if not v:
        return None
    return str(v)[:10]


def fetch_one(ticker: str) -> dict:
    out = {
        "ticker": ticker,
        "name": ticker,
        "price": None,
        "annual_div": None,
        "last_div_amount": None,
        "last_div_date": None,
        "next_ex_div": None,
        "currency": "",
        "yahoo_yield": None,
        "error": None,
    }

    if not FMP_KEY:
        out["error"] = "伺服器尚未設定 FMP API Key"
        return out

    # 1) Quote — 現價、名稱、年息、息率（quote 常已含）
    qlist = fmp_get(f"quote/{ticker}")
    if isinstance(qlist, dict) and qlist.get("error"):
        out["error"] = qlist["error"]
        return out
    if not isinstance(qlist, list) or len(qlist) == 0:
        out["error"] = "查無此代號或 API 無回傳"
        return out

    q = qlist[0] if isinstance(qlist[0], dict) else {}
    if q.get("name"):
        out["name"] = q["name"]
    price = _f(q.get("price"))
    if price is not None and price > 0:
        out["price"] = round(price, 4)

    # quote 內常見欄位
    for key in ("lastDiv", "lastDividend", "dividend"):
        d = _f(q.get(key))
        if d is not None and d > 0:
            # lastDiv 有時是最近一季，有時是年；下面再用 metrics 校正
            out["last_div_amount"] = round(d, 4)
            break

    y = _f(q.get("dividendYield") or q.get("yield"))
    if y is not None and y > 0:
        # FMP 有時是 0.005（小數）、有時是 0.5（已是百分比）
        out["yahoo_yield"] = round(y * 100, 2) if y < 0.2 else round(y, 2)

    time.sleep(0.2)

    # 2) Profile — 幣別、公司名
    plist = fmp_get(f"profile/{ticker}")
    if isinstance(plist, list) and plist:
        p = plist[0]
        if p.get("companyName") and (not out["name"] or out["name"] == ticker):
            out["name"] = p["companyName"]
        if p.get("currency"):
            out["currency"] = p["currency"]
        # profile 有時有 lastDiv / price
        if out["price"] is None:
            pr = _f(p.get("price"))
            if pr:
                out["price"] = round(pr, 4)
        ld = _f(p.get("lastDiv"))
        if ld and out["last_div_amount"] is None:
            out["last_div_amount"] = round(ld, 4)

    time.sleep(0.2)

    # 3) Key metrics TTM — 股息殖利率、每股股息
    metrics = fmp_get(f"key-metrics-ttm/{ticker}")
    if isinstance(metrics, list) and metrics:
        m = metrics[0]
        # 每股股息（年）
        for key in (
            "dividendPerShareTTM",
            "dividendPerShare",
            "netIncomePerShareTTM",  # 不要用這個
        ):
            if key.startswith("net"):
                continue
            val = _f(m.get(key))
            if val is not None and val > 0:
                out["annual_div"] = round(val, 4)
                break
        dy = _f(m.get("dividendYieldTTM") or m.get("dividendYield"))
        if dy is not None and dy > 0:
            out["yahoo_yield"] = round(dy * 100, 2) if dy < 0.2 else round(dy, 2)

    time.sleep(0.2)

    # 4) Ratios TTM — 再補一次 yield
    if out["yahoo_yield"] is None:
        ratios = fmp_get(f"ratios-ttm/{ticker}")
        if isinstance(ratios, list) and ratios:
            r0 = ratios[0]
            dy = _f(r0.get("dividendYieldTTM") or r0.get("dividendYielTTM") or r0.get("dividendYield"))
            if dy is not None and dy > 0:
                out["yahoo_yield"] = round(dy * 100, 2) if dy < 0.2 else round(dy, 2)
        time.sleep(0.15)

    # 5) 歷史派息 — 最近一次 + 估算年息
    div_data = fmp_get(f"historical-price-full/stock_dividend/{ticker}")
    hist = []
    if isinstance(div_data, dict) and not div_data.get("error"):
        hist = div_data.get("historical") or []
    elif isinstance(div_data, list):
        hist = div_data

    if hist:
        # 已按日期新到舊
        latest = hist[0]
        amt = _f(latest.get("adjDividend") or latest.get("dividend"))
        if amt is not None:
            out["last_div_amount"] = round(amt, 4)
        out["last_div_date"] = _date(latest.get("date") or latest.get("paymentDate"))
        out["next_ex_div"] = _date(latest.get("date"))  # 最近除淨日參考

        # 用近 12 個月派息加總當年息
        if out["annual_div"] is None and amt is not None:
            total = 0.0
            count = 0
            for h in hist[:8]:
                a = _f(h.get("adjDividend") or h.get("dividend"))
                if a is not None:
                    total += a
                    count += 1
            # 若一年約 4 次，取最近 4 筆；否則用最近一筆 × 頻率
            if count >= 4:
                out["annual_div"] = round(sum(
                    _f(h.get("adjDividend") or h.get("dividend")) or 0 for h in hist[:4]
                ), 4)
            elif count >= 1:
                # 預設季息
                out["annual_div"] = round(amt * 4, 4)

            # yield from price
            if out["yahoo_yield"] is None and out["price"] and out["annual_div"]:
                out["yahoo_yield"] = round(out["annual_div"] / out["price"] * 100, 2)

    # 互相補齊
    if out["annual_div"] is None and out["price"] and out["yahoo_yield"]:
        out["annual_div"] = round(out["price"] * (out["yahoo_yield"] / 100.0), 4)
    if out["yahoo_yield"] is None and out["price"] and out["annual_div"]:
        out["yahoo_yield"] = round(out["annual_div"] / out["price"] * 100, 2)

    # lastDiv 若像是季息且尚無年息
    if out["annual_div"] is None and out["last_div_amount"]:
        out["annual_div"] = round(out["last_div_amount"] * 4, 4)
        if out["price"] and out["yahoo_yield"] is None:
            out["yahoo_yield"] = round(out["annual_div"] / out["price"] * 100, 2)

    if out["price"] is None and out["annual_div"] is None:
        out["error"] = out.get("error") or "查無報價／股息資料"

    return out


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/quotes", methods=["POST"])
def api_quotes():
    data = request.get_json(silent=True) or {}
    tickers = data.get("tickers") or []
    if not isinstance(tickers, list):
        return jsonify({"error": "tickers 必須是陣列"}), 400

    if not FMP_KEY:
        return jsonify({
            "error": "伺服器尚未設定 FMP_API_KEY。請到 Render → Environment 新增。",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "results": [],
        }), 200

    seen = set()
    clean = []
    for t in tickers:
        t = str(t).strip().upper()
        if t and t not in seen:
            seen.add(t)
            clean.append(t)

    # 免費約 250 次／天；每檔約 3～5 次請求，建議一次 ≤10 檔
    if len(clean) > 10:
        return jsonify({"error": "免費額度有限，一次最多 10 檔。請分批更新。"}), 400

    results = []
    for t in clean:
        results.append(fetch_one(t))
        time.sleep(0.25)

    return jsonify({
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
        "note": "FMP 免費約 250 次/天；每檔會用數次請求",
        "provider": "FMP",
    })


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.now().isoformat(),
        "api_key_set": bool(FMP_KEY),
        "provider": "FMP",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  股息投資組合 — FMP 版")
    print(f"  API Key 已設定: {bool(FMP_KEY)}")
    print(f"  http://127.0.0.1:{port}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)
