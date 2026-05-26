#!/usr/bin/env python3
"""
Export daily options IV data to JSON for batch import into the options calculator.

Usage:
    python3 export-iv-data.py AAPL NVDA TSLA
    # Outputs: iv-data-YYYYMMDD.json

    python3 export-iv-data.py --tickers AAPL,NVDA,TSLA --output my-iv.json
"""

import json
import sys
import argparse
import urllib.request
from datetime import datetime

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

            # Only include expiries that have IV data
            if expiry_entry["calls"] or expiry_entry["puts"]:
                ticker_data["expiries"].append(expiry_entry)

        return ticker_data
    except Exception as e:
        print(f"  [FAIL] {ticker.upper()}: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Export options IV data to JSON")
    parser.add_argument("tickers", nargs="*", help="Stock tickers (e.g. AAPL NVDA TSLA)")
    parser.add_argument("--tickers", dest="ticker_list", help="Comma-separated tickers (e.g. AAPL,NVDA,TSLA)")
    parser.add_argument("--output", "-o", default=None, help="Output JSON file (default: iv-data-YYYYMMDD.json)")
    args = parser.parse_args()

    # Collect tickers from both positional args and --tickers
    tickers = list(args.tickers)
    if args.ticker_list:
        tickers.extend([t.strip().upper() for t in args.ticker_list.split(",")])

    if not tickers:
        print("Usage: python3 export-iv-data.py AAPL NVDA TSLA")
        print("   or: python3 export-iv-data.py --tickers AAPL,NVDA,TSLA")
        sys.exit(1)

    print(f"Fetching IV data for {len(tickers)} tickers...")
    output = {
        "version": 1,
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tickers": {},
    }

    success_count = 0
    for ticker in tickers:
        print(f"  [{success_count+1}/{len(tickers)}] {ticker}...", end="", flush=True)
        data = fetch_yahoo_iv(ticker)
        if data and data["expiries"]:
            output["tickers"][ticker.upper()] = data
            print(f" OK ({len(data['expiries'])} expiries)")
            success_count += 1
        else:
            print(" FAIL")

    output_file = args.output or f"iv-data-{datetime.now().strftime('%Y%m%d')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {success_count}/{len(tickers)} tickers exported to: {output_file}")
    print(f"  Total expiries: {sum(len(t['expiries']) for t in output['tickers'].values())}")
    print(f"  Total IV entries: {sum(sum(len(e['calls']) + len(e['puts']) for e in t['expiries']) for t in output['tickers'].values())}")


if __name__ == "__main__":
    main()
