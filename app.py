#!/usr/bin/env python3
"""
股息投資組合追蹤 — FMP Stable API 版
環境變數：FMP_API_KEY
文件：https://financialmodelingprep.com/stable/
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
FMP_BASE = "https://financialmodelingprep.com/stable"


def fmp_get(endpoint: str, params: dict = None):
    if not FMP_KEY:
        return {"error": "尚未設定 FMP_API_KEY"}
    params = dict(params or {})
    params["apikey"] = FMP_KEY
    try:
        r = requests.get(f"{FMP_BASE}/{endpoint}", params=params, timeout=25)
        data = r.json()
        if isinstance(data, dict) and data.get("Error Message"):
            return {"error": data["Error Message"]}
        if r.status_code != 200:
            msg = data.get("Error Message") if isinstance(data, dict) else f"HTTP {r.status_code}"
            return {"error": msg or f"HTTP {r.status_code}"}
        return data
    except Exception as e:
        return {"error": str(e)}


def _f(v):
    if v is None or v == "" or v == "None":
        return None
    try:
        x = float(v)
        if x != x:
            return None
        return x
    except (TypeError, ValueError):
        return None


def _date(v):
    if not v:
        return None
    return str(v)[:10]


def _first_row(data):
    if isinstance(data, list) and data:
        return data[0] if isinstance(data[0], dict) else {}
    if isinstance(data, dict) and not data.get("error"):
        return data
    return {}


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

    # 1) Quote
    qdata = fmp_get("quote", {"symbol": ticker})
    if isinstance(qdata, dict) and qdata.get("error"):
        out["error"] = qdata["error"]
        return out
    q = _first_row(qdata)
    if not q:
        out["error"] = "查無此代號報價"
        return out

    if q.get("name"):
        out["name"] = q["name"]
    price = _f(q.get("price"))
    if price is not None and price > 0:
        out["price"] = round(price, 4)

    time.sleep(0.2)

    # 2) Profile — 幣別、公司名、lastDiv
    pdata = fmp_get("profile", {"symbol": ticker})
    if not (isinstance(pdata, dict) and pdata.get("error")):
        p = _first_row(pdata)
        if p.get("companyName") and (not out["name"] or out["name"] == ticker):
            out["name"] = p["companyName"]
        if p.get("currency"):
            out["currency"] = p["currency"]
        if out["price"] is None:
            pr = _f(p.get("price"))
            if pr:
                out["price"] = round(pr, 4)
        ld = _f(p.get("lastDiv"))
        if ld and ld > 0:
            out["last_div_amount"] = round(ld, 4)
            # lastDiv 常為最近一季 → 年息約 ×4（後面用 dividends 校正）
            if out["annual_div"] is None:
                out["annual_div"] = round(ld * 4, 4)

    time.sleep(0.2)

    # 3) Dividends — 派息歷史／殖利率／頻率
    ddata = fmp_get("dividends", {"symbol": ticker})
    hist = []
    if isinstance(ddata, list):
        hist = [x for x in ddata if isinstance(x, dict)]
    elif isinstance(ddata, dict) and not ddata.get("error"):
        hist = ddata.get("historical") or ddata.get("data") or []

    if hist:
        latest = hist[0]
        amt = _f(latest.get("adjDividend") or latest.get("dividend"))
        if amt is not None and amt > 0:
            out["last_div_amount"] = round(amt, 4)
        out["last_div_date"] = _date(
            latest.get("paymentDate") or latest.get("date") or latest.get("recordDate")
        )
        out["next_ex_div"] = _date(latest.get("date") or latest.get("recordDate"))

        y = _f(latest.get("yield"))
        if y is not None and y > 0:
            # 文件範例 yield 約 0.35 表示 0.35%
            out["yahoo_yield"] = round(y, 2) if y >= 0.05 else round(y * 100, 2)

        freq = (latest.get("frequency") or "").lower()
        mult = 4
        if "month" in freq:
            mult = 12
        elif "semi" in freq or "half" in freq:
            mult = 2
        elif "annual" in freq or "year" in freq:
            mult = 1
        elif "quarter" in freq:
            mult = 4

        # 近一年派息加總（最多取 4～12 筆）
        recent_amts = []
        for h in hist[:12]:
            a = _f(h.get("adjDividend") or h.get("dividend"))
            if a is not None and a > 0:
                recent_amts.append(a)
        if len(recent_amts) >= 4:
            out["annual_div"] = round(sum(recent_amts[:4]), 4)
        elif amt is not None and amt > 0:
            out["annual_div"] = round(amt * mult, 4)

    # 互相補齊
    if out["annual_div"] is None and out["price"] and out["yahoo_yield"]:
        out["annual_div"] = round(out["price"] * (out["yahoo_yield"] / 100.0), 4)
    if out["yahoo_yield"] is None and out["price"] and out["annual_div"]:
        out["yahoo_yield"] = round(out["annual_div"] / out["price"] * 100, 2)

    if out["price"] is None and out["annual_div"] is None:
        out["error"] = "查無報價／股息資料"

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

    if len(clean) > 10:
        return jsonify({"error": "免費額度有限，一次最多 10 檔。請分批更新。"}), 400

    results = []
    for t in clean:
        results.append(fetch_one(t))
        time.sleep(0.25)

    return jsonify({
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
        "note": "FMP Stable API；免費額度有限，請勿頻繁大量更新",
        "provider": "FMP",
    })


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.now().isoformat(),
        "api_key_set": bool(FMP_KEY),
        "provider": "FMP",
        "api_base": "stable",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  股息投資組合 — FMP Stable")
    print(f"  API Key 已設定: {bool(FMP_KEY)}")
    print(f"  http://127.0.0.1:{port}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)
