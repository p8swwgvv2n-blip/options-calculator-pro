#!/usr/bin/env python3
"""
期权 IV 数据导出工具 — 双击运行
自动抓取 Yahoo Finance 期权链 IV 数据，导出为 JSON 供网页批量导入。

用法：
  Mac: 双击本文件，或在终端运行 python3 导出期权IV.py
  Win: 双击本文件，或在 CMD 运行 python 导出期权IV.py
"""

import json
import sys
import urllib.request
from datetime import datetime

def check_deps():
    """Check if urllib is available (stdlib, always present)."""
    return True

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


def interactive_mode():
    """Simple text UI — ask tickers one by one."""
    print("=" * 50)
    print("  期权 IV 数据导出工具")
    print("=" * 50)
    print()
    print("请输入股票代码（多个用空格或逗号隔开），例如：")
    print("  AAPL NVDA TSLA")
    print("  或 AMD,AMZN,GOOGL")
    print()

    user_input = input("股票代码 > ").strip()
    if not user_input:
        print("未输入股票代码，已退出。")
        return

    tickers = [t.strip().upper() for t in user_input.replace(",", " ").split() if t.strip()]
    print()
    print(f"开始抓取 {len(tickers)} 只股票的 IV 数据...")
    print()

    output = {
        "version": 1,
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tickers": {},
    }

    success_count = 0
    for i, ticker in enumerate(tickers, 1):
        print(f"  [{i}/{len(tickers)}] {ticker}...", end="", flush=True)
        data = fetch_yahoo_iv(ticker)
        if data and data["expiries"]:
            output["tickers"][ticker] = data
            total_iv = sum(len(e["calls"]) + len(e["puts"]) for e in data["expiries"])
            print(f" OK ({len(data['expiries'])}个到期日, {total_iv}条IV)")
            success_count += 1
        else:
            print(" 失败 (可能被 Yahoo 限流，稍后重试)")

    if success_count == 0:
        print()
        print("未成功获取任何数据，请检查网络连接后重试。")
        input("\n按回车退出...")
        return

    output_file = f"iv-data-{datetime.now().strftime('%Y%m%d')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total_expiries = sum(len(t["expiries"]) for t in output["tickers"].values())
    total_iv = sum(sum(len(e["calls"]) + len(e["puts"]) for e in t["expiries"]) for t in output["tickers"].values())

    print()
    print("=" * 50)
    print(f"  导出完成！")
    print(f"  文件: {output_file}")
    print(f"  股票: {success_count} 只")
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
        interactive_mode()
    except KeyboardInterrupt:
        print("\n已取消。")
    except Exception as e:
        print(f"错误: {e}")
        input("\n按回车退出...")
