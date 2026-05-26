#!/usr/bin/env python3
"""
期权 IV 数据定时导出 — 按 OpenClaw 逻辑
每天自动抓取预设股票的 IV 数据，保存到历史文件夹。

用法：
  Mac: 加入 crontab 或 launchd
       0 9 * * 1-5 cd /path/to/folder && python3 定时导出期权IV.py
  Win: 加入 Windows 任务计划程序
       每天 9:00 运行 python 定时导出期权IV.py
"""

import json
import sys
import os
import urllib.request
from datetime import datetime

DEFAULT_TICKERS = ["AMD", "AMZN", "GOOGL", "UNH", "TSLA", "AAPL", "NVDA", "MSFT", "META"]

def fetch_yahoo_iv(ticker):
    url = f"https://query2.finance.yahoo.com/v7/finance/options/{ticker.upper()}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        result = data["optionChain"]["result"][0]
        meta = result.get("quote", {})

        ticker_data = {
            "symbol": ticker.upper(),
            "price": meta.get("regularMarketPrice"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "expiries": [],
        }

        for opt in result.get("options", []):
            exp_date = opt.get("expirationDate")
            exp_str = datetime.utcfromtimestamp(exp_date).strftime("%Y-%m-%d") if exp_date else "?"
            expiry_entry = {
                "date": exp_str,
                "timestamp": exp_date,
                "calls": [],
                "puts": [],
            }
            for c in opt.get("calls", []):
                iv = c.get("impliedVolatility")
                if iv is not None:
                    expiry_entry["calls"].append({
                        "strike": c["strike"],
                        "iv": round(iv * 100, 2),
                        "lastPrice": c.get("lastPrice"),
                        "bid": c.get("bid"),
                        "ask": c.get("ask"),
                        "volume": c.get("volume"),
                        "openInterest": c.get("openInterest"),
                    })
            for p in opt.get("puts", []):
                iv = p.get("impliedVolatility")
                if iv is not None:
                    expiry_entry["puts"].append({
                        "strike": p["strike"],
                        "iv": round(iv * 100, 2),
                        "lastPrice": p.get("lastPrice"),
                        "bid": p.get("bid"),
                        "ask": p.get("ask"),
                        "volume": p.get("volume"),
                        "openInterest": p.get("openInterest"),
                    })
            if expiry_entry["calls"] or expiry_entry["puts"]:
                ticker_data["expiries"].append(expiry_entry)
        return ticker_data
    except Exception:
        return None


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    history_dir = os.path.join(script_dir, "iv-history")
    os.makedirs(history_dir, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    output_file = os.path.join(history_dir, f"iv-data-{today}.json")

    # Skip if today's file already exists
    if os.path.exists(output_file):
        print(f"SKIP: {output_file} already exists")
        return

    output = {
        "version": 1,
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tickers": {},
    }

    success_count = 0
    for ticker in DEFAULT_TICKERS:
        data = fetch_yahoo_iv(ticker)
        if data and data["expiries"]:
            output["tickers"][ticker] = data
            total_iv = sum(len(e["calls"]) + len(e["puts"]) for e in data["expiries"])
            print(f"  {ticker} OK ({len(data['expiries'])} expiries, {total_iv} IV)")
            success_count += 1
        else:
            print(f"  {ticker} FAIL")

    if success_count == 0:
        print("FAIL: no data fetched")
        sys.exit(1)

    # Also write latest to script dir for easy access
    latest_file = os.path.join(script_dir, "iv-data-latest.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total_expiries = sum(len(t["expiries"]) for t in output["tickers"].values())
    total_iv = sum(sum(len(e["calls"]) + len(e["puts"]) for e in t["expiries"]) for t in output["tickers"].values())
    print(f"OK: {output_file} ({success_count}/{len(DEFAULT_TICKERS)} tickers, {total_expiries} expiries, {total_iv} IV entries)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
