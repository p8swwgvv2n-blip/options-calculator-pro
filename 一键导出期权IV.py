#!/usr/bin/env python3
"""
期权 IV 数据导出工具 — 双击运行，自动导出预设股票

预设股票：AMD, AMZN, GOOGL, UNH, TSLA, AAPL, NVDA, MSFT, META

用法：
  Mac: 双击本文件，或 python3 一键导出期权IV.py
  Win: 双击本文件，或 python 一键导出期权IV.py
"""

import json
import sys
import os
import urllib.request
from datetime import datetime

# ===== 预设股票代码（跟网页热门美股一致）=====
DEFAULT_TICKERS = ["AMD", "AMZN", "GOOGL", "UNH", "TSLA", "AAPL", "NVDA", "MSFT", "META"]

def fetch_yahoo_iv(ticker):
    """Fetch all options IV data for a ticker from Yahoo Finance."""
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
    except Exception as e:
        return None


def export_iv(tickers=None, output_dir=None):
    """Export IV data for given tickers to JSON."""
    if tickers is None:
        tickers = DEFAULT_TICKERS

    output = {
        "version": 1,
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tickers": {},
    }

    success_count = 0
    for i, ticker in enumerate(tickers, 1):
        data = fetch_yahoo_iv(ticker)
        if data and data["expiries"]:
            output["tickers"][ticker] = data
            total_iv = sum(len(e["calls"]) + len(e["puts"]) for e in data["expiries"])
            print(f"  [{i}/{len(tickers)}] {ticker} OK ({len(data['expiries'])}个到期日, {total_iv}条IV)")
            success_count += 1
        else:
            print(f"  [{i}/{len(tickers)}] {ticker} 失败")

    if success_count == 0:
        print("\n未成功获取任何数据，请检查网络连接后重试。")
        return None

    # Determine output file path
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(output_dir, f"iv-data-{datetime.now().strftime('%Y%m%d')}.json")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total_expiries = sum(len(t["expiries"]) for t in output["tickers"].values())
    total_iv = sum(sum(len(e["calls"]) + len(e["puts"]) for e in t["expiries"]) for t in output["tickers"].values())

    return output_file, success_count, len(tickers), total_expiries, total_iv


def interactive_mode():
    """Run with preset tickers, no input needed."""
    print("=" * 50)
    print("  期权 IV 数据导出工具")
    print("=" * 50)
    print()
    print(f"预设股票: {', '.join(DEFAULT_TICKERS)}")
    print(f"正在抓取 {len(DEFAULT_TICKERS)} 只股票的 IV 数据...")
    print()

    result = export_iv()
    if result is None:
        input("\n按回车退出...")
        return

    output_file, success, total, total_expiries, total_iv = result

    print()
    print("=" * 50)
    print("  导出完成！")
    print(f"  文件: {output_file}")
    print(f"  成功: {success}/{total} 只股票")
    print(f"  到期日: {total_expiries} 个")
    print(f"  IV 条目: {total_iv} 条")
    print()
    print("下一步：将 JSON 文件传到另一台电脑，")
    print("       在期权计算器网页点击「批量导入 IV 数据」导入。")
    print("=" * 50)
    print()
    input("按回车退出...")


if __name__ == "__main__":
    try:
        # Check if --cron flag is passed (for scheduled task mode)
        if "--cron" in sys.argv:
            # Silent mode for cron: just export and exit
            result = export_iv()
            if result:
                output_file, success, total, total_expiries, total_iv = result
                print(f"OK: {output_file} ({success}/{total} tickers, {total_iv} IV entries)")
            else:
                print("FAIL: no data fetched")
                sys.exit(1)
        else:
            interactive_mode()
    except KeyboardInterrupt:
        print("\n已取消。")
    except Exception as e:
        print(f"错误: {e}")
        input("\n按回车退出...")
