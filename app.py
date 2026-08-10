#!/usr/bin/env python3
"""
股息投資組合追蹤 — 網頁版（Twelve Data）
雲端請設定環境變數 TWELVE_DATA_API_KEY
"""

from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
import time
import requests
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__)

TD_API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "").strip()
TD_BASE = "https://api.twelvedata.com"


def td_get(endpoint: str, params: dict) -> dict:
    if not TD_API_KEY:
        return {"status": "error", "message": "尚未設定 TWELVE_DATA_API_KEY"}
    params = dict(params)
    params["apikey"] = TD_API_KEY
    try:
        r = requests.get(f"{TD_BASE}/{endpoint}", params=params, timeout=25)
        data = r.json()
        return data
    except Exception as e:
        return {"status": "error", "message": str(e)}


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

    if not TD_API_KEY:
        out["error"] = "伺服器尚未設定 Twelve Data API Key"
        return out

    # 1) Quote — 現價、名稱、幣別
    q = td_get("quote", {"symbol": ticker})
    if q.get("status") == "error" or q.get("code"):
        out["error"] = q.get("message") or q.get("status") or "Quote 請求失敗"
        return out

    if q.get("name"):
        out["name"] = q["name"]
    if q.get("currency"):
        out["currency"] = q["currency"]

    close = q.get("close") or q.get("previous_close")
    if close is not None:
        try:
            out["price"] = round(float(close), 4)
        except (TypeError, ValueError):
            pass

    time.sleep(0.35)

    # 2) Statistics — 年息、息率、除淨日
    st = td_get("statistics", {"symbol": ticker})
    if st.get("status") == "error" or st.get("code"):
        # 有價格也算部分成功
        if not out["price"]:
            out["error"] = st.get("message") or "Statistics 請求失敗"
        return out

    stats = st.get("statistics") or {}
    divs = stats.get("dividends_and_splits") or {}

    # 年息：優先 forward，其次 trailing
    for key in ("forward_annual_dividend_rate", "trailing_annual_dividend_rate"):
        val = divs.get(key)
        if val is not None and val != "" and val != 0:
            try:
                out["annual_div"] = round(float(val), 4)
                break
            except (TypeError, ValueError):
                pass

    # 息率（小數 → 百分比）
    for key in ("forward_annual_dividend_yield", "trailing_annual_dividend_yield"):
        val = divs.get(key)
        if val is not None and val != "":
            try:
                y = float(val)
                # Twelve Data 給的是小數（如 0.0034 = 0.34%）
                out["yahoo_yield"] = round(y * 100, 2) if y < 1 else round(y, 2)
                break
            except (TypeError, ValueError):
                pass

    ex = divs.get("ex_dividend_date") or ""
    if ex and ex not in ("None", "-", "null"):
        out["next_ex_div"] = str(ex)[:10]

    dd = divs.get("dividend_date") or ""
    if dd and dd not in ("None", "-", "null"):
        out["last_div_date"] = str(dd)[:10]

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

    if not TD_API_KEY:
        return jsonify({
            "error": "伺服器尚未設定 TWELVE_DATA_API_KEY。請到 Render Environment 新增。",
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

    # 免費約 800 credits/天；quote+statistics 各約 1 credit，一次建議 ≤15 檔
    if len(clean) > 15:
        return jsonify({"error": "一次最多查詢 15 檔，請分批更新。"}), 400

    results = []
    for t in clean:
        results.append(fetch_one(t))
        time.sleep(0.3)

    return jsonify({
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
        "note": "Twelve Data 免費約 800 次/天",
        "provider": "Twelve Data",
    })


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.now().isoformat(),
        "api_key_set": bool(TD_API_KEY),
        "provider": "Twelve Data",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  股息投資組合追蹤 — Twelve Data 版")
    print(f"  API Key 已設定: {bool(TD_API_KEY)}")
    print(f"  本機：http://127.0.0.1:{port}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)
