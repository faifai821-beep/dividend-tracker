#!/usr/bin/env python3
"""
股息投資組合追蹤 — 網頁版
執行：python app.py
然後瀏覽器開啟 http://127.0.0.1:5000
"""

from flask import Flask, render_template, request, jsonify
import yfinance as yf
from datetime import datetime, timezone
import time
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__)

def fetch_one(ticker: str) -> dict:
    """抓取單一股票的股價與派息資料"""
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
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        out["name"] = info.get("shortName") or info.get("longName") or ticker
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        if price is not None:
            out["price"] = round(float(price), 4)

        annual = info.get("dividendRate") or info.get("trailingAnnualDividendRate")
        if annual is not None:
            out["annual_div"] = round(float(annual), 4)

        dy = info.get("dividendYield")
        if dy is not None:
            out["yahoo_yield"] = round(float(dy), 2)

        out["currency"] = info.get("currency") or ""

        try:
            divs = t.dividends
            if divs is not None and len(divs) > 0:
                out["last_div_amount"] = round(float(divs.iloc[-1]), 4)
                last_dt = divs.index[-1]
                if hasattr(last_dt, "strftime"):
                    out["last_div_date"] = last_dt.strftime("%Y-%m-%d")
                else:
                    out["last_div_date"] = str(last_dt)[:10]
        except Exception:
            pass

        ex_ts = info.get("exDividendDate")
        if ex_ts:
            try:
                if isinstance(ex_ts, (int, float)):
                    dt = datetime.fromtimestamp(ex_ts, tz=timezone.utc)
                    out["next_ex_div"] = dt.strftime("%Y-%m-%d")
                else:
                    out["next_ex_div"] = str(ex_ts)[:10]
            except Exception:
                pass

    except Exception as e:
        out["error"] = str(e)
    return out


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/quotes", methods=["POST"])
def api_quotes():
    """接收 tickers 陣列，回傳最新股價與派息資料"""
    data = request.get_json(silent=True) or {}
    tickers = data.get("tickers") or []
    if not isinstance(tickers, list):
        return jsonify({"error": "tickers 必須是陣列"}), 400

    # 去重並限制數量
    seen = set()
    clean = []
    for t in tickers:
        t = str(t).strip().upper()
        if t and t not in seen:
            seen.add(t)
            clean.append(t)
    if len(clean) > 30:
        return jsonify({"error": "一次最多查詢 30 檔"}), 400

    results = []
    for t in clean:
        results.append(fetch_one(t))
        time.sleep(0.25)  # 避免請求過快

    return jsonify({
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  股息投資組合追蹤 — 網頁版")
    print(f"  本機請開啟：http://127.0.0.1:{port}")
    print("=" * 50)
    # 本機與雲端部署都適用（Render 等會注入 PORT）
    app.run(host="0.0.0.0", port=port, debug=False)
