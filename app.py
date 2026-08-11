#!/usr/bin/env python3
"""
股息投資組合追蹤 — Finnhub 版
Render 環境變數：FINNHUB_API_KEY
"""

from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import os
import time
import requests
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__)

FH_KEY = os.environ.get("FINNHUB_API_KEY", "").strip()
FH_BASE = "https://finnhub.io/api/v1"


def fh_get(path: str, params: dict = None) -> dict:
    if not FH_KEY:
        return {"error": "尚未設定 FINNHUB_API_KEY"}
    params = dict(params or {})
    params["token"] = FH_KEY
    try:
        r = requests.get(f"{FH_BASE}/{path}", params=params, timeout=20)
        data = r.json()
        if r.status_code != 200:
            return {"error": data.get("error") or f"HTTP {r.status_code}"}
        return data if isinstance(data, dict) else {"data": data}
    except Exception as e:
        return {"error": str(e)}


def _to_float(v):
    if v is None or v == "" or v == "None":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fmt_date(v):
    """Finnhub 有時給 unix、有時給 YYYY-MM-DD"""
    if v is None or v == "" or v == 0:
        return None
    if isinstance(v, (int, float)):
        try:
            # 毫秒或秒
            ts = v / 1000 if v > 1e12 else v
            return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        except Exception:
            return None
    s = str(v)[:10]
    return s if len(s) >= 8 else None


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

    if not FH_KEY:
        out["error"] = "伺服器尚未設定 Finnhub API Key"
        return out

    # 1) 現價
    q = fh_get("quote", {"symbol": ticker})
    if q.get("error"):
        out["error"] = q["error"]
        return out
    # c = current price；若為 0 可能是無效代號
    price = _to_float(q.get("c"))
    if price is not None and price > 0:
        out["price"] = round(price, 4)
    elif _to_float(q.get("pc")):
        out["price"] = round(_to_float(q.get("pc")), 4)

    time.sleep(0.25)

    # 2) 公司名稱、幣別
    prof = fh_get("stock/profile2", {"symbol": ticker})
    if not prof.get("error"):
        if prof.get("name"):
            out["name"] = prof["name"]
        if prof.get("currency"):
            out["currency"] = prof["currency"]

    time.sleep(0.25)

    # 3) 基本面指標（殖利率、每股股息）
    met = fh_get("stock/metric", {"symbol": ticker, "metric": "all"})
    metric = (met.get("metric") or {}) if not met.get("error") else {}

    # 年息：優先年度每股股息
    for key in (
        "dividendPerShareAnnual",
        "dividendPerShareTTM",
        "dividendsPerShareTTM",
        "dividendPerShare",
    ):
        val = _to_float(metric.get(key))
        if val is not None and val > 0:
            out["annual_div"] = round(val, 4)
            break

    # 殖利率（Finnhub 多為百分比數值，如 0.5 代表 0.5%，或 0.005 代表小數）
    for key in (
        "dividendYieldIndicatedAnnual",
        "dividendYieldTTM",
        "dividendYield",
    ):
        val = _to_float(metric.get(key))
        if val is not None and val > 0:
            # 若 < 0.2 多半是小數（0.005 = 0.5%），轉成百分比顯示
            if val < 0.2:
                out["yahoo_yield"] = round(val * 100, 2)
            else:
                out["yahoo_yield"] = round(val, 2)
            break

    # 若有殖利率與現價但無年息 → 反推年息
    if out["annual_div"] is None and out["price"] and out["yahoo_yield"]:
        # yahoo_yield 已是百分比數字
        out["annual_div"] = round(out["price"] * (out["yahoo_yield"] / 100.0), 4)

    # 若有年息與現價但無殖利率 → 反推
    if out["yahoo_yield"] is None and out["price"] and out["annual_div"]:
        out["yahoo_yield"] = round(out["annual_div"] / out["price"] * 100, 2)

    ex = metric.get("exDividendDate") or metric.get("dividendDate")
    out["next_ex_div"] = _fmt_date(ex)

    time.sleep(0.25)

    # 4) 嘗試最近派息（免費方案有時可用）
    try:
        to_d = datetime.utcnow().strftime("%Y-%m-%d")
        from_d = (datetime.utcnow() - timedelta(days=400)).strftime("%Y-%m-%d")
        divs = fh_get("stock/dividend", {"symbol": ticker, "from": from_d, "to": to_d})
        # 可能是 list 或 {"data": [...]} 或 error
        rows = []
        if isinstance(divs, list):
            rows = divs
        elif isinstance(divs, dict) and not divs.get("error"):
            rows = divs.get("data") or divs.get("dividends") or []
            if not rows and "amount" in divs:
                rows = [divs]
        if rows:
            # 依日期排序取最新
            def sort_key(x):
                return str(x.get("date") or x.get("exDate") or x.get("payDate") or "")

            rows = sorted(rows, key=sort_key, reverse=True)
            latest = rows[0]
            amt = _to_float(latest.get("amount") or latest.get("adjustedAmount"))
            if amt is not None:
                out["last_div_amount"] = round(amt, 4)
            out["last_div_date"] = _fmt_date(
                latest.get("date") or latest.get("exDate") or latest.get("payDate")
            )
            if not out["next_ex_div"]:
                out["next_ex_div"] = _fmt_date(latest.get("exDate") or latest.get("date"))
            # 若仍無年息：假設季息 × 4
            if out["annual_div"] is None and amt is not None:
                out["annual_div"] = round(amt * 4, 4)
                if out["price"]:
                    out["yahoo_yield"] = round(out["annual_div"] / out["price"] * 100, 2)
    except Exception:
        pass

    if out["price"] is None and out["annual_div"] is None and not out["error"]:
        out["error"] = "查無資料（代號可能不支援或免費方案限制）"

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

    if not FH_KEY:
        return jsonify({
            "error": "伺服器尚未設定 FINNHUB_API_KEY。請到 Render → Environment 新增。",
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

    if len(clean) > 20:
        return jsonify({"error": "一次最多查詢 20 檔，請分批更新。"}), 400

    results = []
    for t in clean:
        results.append(fetch_one(t))
        time.sleep(0.2)

    return jsonify({
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
        "note": "Finnhub 免費版；部分股息欄位可能受限",
        "provider": "Finnhub",
    })


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.now().isoformat(),
        "api_key_set": bool(FH_KEY),
        "provider": "Finnhub",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  股息投資組合 — Finnhub 版")
    print(f"  API Key 已設定: {bool(FH_KEY)}")
    print(f"  http://127.0.0.1:{port}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)
