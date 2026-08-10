#!/usr/bin/env python3
"""
股息投資組合追蹤 — 網頁版（Alpha Vantage）
執行：python app.py
雲端請設定環境變數 ALPHA_VANTAGE_API_KEY
"""

from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
import time
import requests
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__)

# 從環境變數讀取 API Key（Render 後台可設定）
AV_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
AV_BASE = "https://www.alphavantage.co/query"


def av_get(params: dict) -> dict:
    """呼叫 Alpha Vantage，回傳 JSON"""
    if not AV_API_KEY:
        return {"Error Message": "尚未設定 ALPHA_VANTAGE_API_KEY"}
    params = dict(params)
    params["apikey"] = AV_API_KEY
    try:
        r = requests.get(AV_BASE, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"Error Message": str(e)}


def fetch_one(ticker: str) -> dict:
    """用 Alpha Vantage 抓單一股票的股價與派息資料"""
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

    if not AV_API_KEY:
        out["error"] = "伺服器尚未設定 Alpha Vantage API Key"
        return out

    # 1) 現價 — GLOBAL_QUOTE
    q = av_get({"function": "GLOBAL_QUOTE", "symbol": ticker})
    if "Error Message" in q:
        out["error"] = q["Error Message"]
        return out
    if "Note" in q:
        out["error"] = q["Note"]
        return out
    if "Information" in q:
        out["error"] = q["Information"]
        return out

    gq = q.get("Global Quote") or {}
    price_str = gq.get("05. price") or gq.get("05. Price")
    if price_str:
        try:
            out["price"] = round(float(price_str), 4)
        except ValueError:
            pass

    time.sleep(0.8)

    # 2) 基本面／派息 — OVERVIEW
    ov = av_get({"function": "OVERVIEW", "symbol": ticker})
    if "Error Message" in ov:
        if not out["price"]:
            out["error"] = ov["Error Message"]
        return out
    if "Note" in ov:
        if not out["price"]:
            out["error"] = ov["Note"]
        return out
    if "Information" in ov:
        if not out["price"]:
            out["error"] = ov["Information"]
        return out

    if not ov.get("Symbol") and not ov.get("Name"):
        if not out["price"]:
            out["error"] = "Alpha Vantage 無此代號資料（可能不支援港股/台股）"
        return out

    out["name"] = ov.get("Name") or ticker
    out["currency"] = ov.get("Currency") or ""

    dps = ov.get("DividendPerShare") or ""
    if dps and dps not in ("None", "-", "0", "0.0"):
        try:
            out["annual_div"] = round(float(dps), 4)
        except ValueError:
            pass

    dy = ov.get("DividendYield") or ""
    if dy and dy not in ("None", "-", "0", "0.0"):
        try:
            val = float(dy)
            if val > 1:
                out["yahoo_yield"] = round(val, 2)
            else:
                out["yahoo_yield"] = round(val * 100, 2)
        except ValueError:
            pass

    ex = ov.get("ExDividendDate") or ""
    if ex and ex not in ("None", "-"):
        out["next_ex_div"] = ex[:10]

    dd = ov.get("DividendDate") or ""
    if dd and dd not in ("None", "-"):
        out["last_div_date"] = dd[:10]

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

    if not AV_API_KEY:
        return jsonify({
            "error": "伺服器尚未設定 ALPHA_VANTAGE_API_KEY。請到 Render 環境變數新增此 Key。",
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

    if len(clean) > 8:
        return jsonify({"error": "免費 API 額度有限，一次最多查詢 8 檔。請分批更新。"}), 400

    results = []
    for t in clean:
        results.append(fetch_one(t))
        time.sleep(0.5)

    return jsonify({
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
        "note": "Alpha Vantage 免費版約 25 次/天，請勿頻繁更新",
    })


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.now().isoformat(),
        "api_key_set": bool(AV_API_KEY),
        "provider": "Alpha Vantage",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  股息投資組合追蹤 — Alpha Vantage 版")
    print(f"  API Key 已設定: {bool(AV_API_KEY)}")
    print(f"  本機請開啟：http://127.0.0.1:{port}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)
