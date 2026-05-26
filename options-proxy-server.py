#!/usr/bin/env python3
"""
Options Data Proxy Server
Serves Yahoo Finance options data to the options calculator web page.
Run this on the same machine where you browse the calculator page.

Usage:
    python3 options-proxy-server.py
    # Server starts at http://127.0.0.1:8765

The web page will fetch data from http://127.0.0.1:8765/
"""

import json
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# --- Yahoo Finance data fetching ---

def fetch_yahoo_quote(ticker):
    """Fetch stock quote from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}?interval=1d&range=5d"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        result = data["chart"]["result"][0]
        meta = result["meta"]
        return {
            "symbol": meta.get("symbol", ticker.upper()),
            "price": meta.get("regularMarketPrice"),
            "change": meta.get("regularMarketChange"),
            "changePercent": meta.get("regularMarketChangePercent"),
            "previousClose": meta.get("chartPreviousClose"),
            "fiftyTwoWeekHigh": meta.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": meta.get("fiftyTwoWeekLow"),
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_yahoo_history(ticker, days=100):
    """Fetch daily OHLC history from Yahoo Finance."""
    range_map = {30: "1mo", 60: "2mo", 100: "3mo", 250: "1y"}
    range_str = range_map.get(days, "3mo")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}?interval=1d&range={range_str}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        result = data["chart"]["result"][0]
        ts = result["timestamp"]
        q = result["indicators"]["quote"][0]
        history = []
        for i in range(len(ts)):
            history.append({
                "date": datetime.utcfromtimestamp(ts[i]).strftime("%Y-%m-%d"),
                "open": q.get("open", [None]*len(ts))[i],
                "high": q.get("high", [None]*len(ts))[i],
                "low": q.get("low", [None]*len(ts))[i],
                "close": q.get("close", [None]*len(ts))[i],
                "volume": q.get("volume", [None]*len(ts))[i],
            })
        return {"symbol": ticker.upper(), "history": history}
    except Exception as e:
        return {"error": str(e)}


def fetch_yahoo_options(ticker):
    """Fetch options chain from Yahoo Finance (all expiries, first expiry's chain)."""
    url = f"https://query2.finance.yahoo.com/v7/finance/options/{ticker.upper()}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        result = data["optionChain"]["result"][0]
        expirations = result.get("expirationDates", [])
        options = result.get("options", [])

        chain = {}
        for opt in options:
            exp_date = opt.get("expirationDate")
            chain[exp_date] = {
                "calls": [{
                    "strike": c["strike"],
                    "lastPrice": c.get("lastPrice"),
                    "bid": c.get("bid"),
                    "ask": c.get("ask"),
                    "volume": c.get("volume"),
                    "openInterest": c.get("openInterest"),
                    "impliedVolatility": c.get("impliedVolatility"),
                    "delta": c.get("delta"),
                    "gamma": c.get("gamma"),
                    "theta": c.get("theta"),
                    "vega": c.get("vega"),
                    "inTheMoney": c.get("inTheMoney"),
                } for c in opt.get("calls", [])],
                "puts": [{
                    "strike": p["strike"],
                    "lastPrice": p.get("lastPrice"),
                    "bid": p.get("bid"),
                    "ask": p.get("ask"),
                    "volume": p.get("volume"),
                    "openInterest": p.get("openInterest"),
                    "impliedVolatility": p.get("impliedVolatility"),
                    "delta": p.get("delta"),
                    "gamma": p.get("gamma"),
                    "theta": p.get("theta"),
                    "vega": p.get("vega"),
                    "inTheMoney": p.get("inTheMoney"),
                } for p in opt.get("puts", [])],
            }

        return {
            "symbol": result.get("quote", {}).get("symbol", ticker.upper()),
            "expirationDates": expirations,
            "chains": chain,
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_yahoo_options_for_expiry(ticker, expiry_ts):
    """Fetch options chain for a specific expiry date."""
    url = f"https://query2.finance.yahoo.com/v7/finance/options/{ticker.upper()}?date={expiry_ts}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        result = data["optionChain"]["result"][0]
        options = result.get("options", [])

        if options:
            opt = options[0]
            return {
                "calls": [{
                    "strike": c["strike"],
                    "lastPrice": c.get("lastPrice"),
                    "bid": c.get("bid"),
                    "ask": c.get("ask"),
                    "volume": c.get("volume"),
                    "openInterest": c.get("openInterest"),
                    "impliedVolatility": c.get("impliedVolatility"),
                    "delta": c.get("delta"),
                    "gamma": c.get("gamma"),
                    "theta": c.get("theta"),
                    "vega": c.get("vega"),
                    "inTheMoney": c.get("inTheMoney"),
                } for c in opt.get("calls", [])],
                "puts": [{
                    "strike": p["strike"],
                    "lastPrice": p.get("lastPrice"),
                    "bid": p.get("bid"),
                    "ask": p.get("ask"),
                    "volume": p.get("volume"),
                    "openInterest": p.get("openInterest"),
                    "impliedVolatility": p.get("impliedVolatility"),
                    "delta": p.get("delta"),
                    "gamma": p.get("gamma"),
                    "theta": p.get("theta"),
                    "vega": p.get("vega"),
                    "inTheMoney": p.get("inTheMoney"),
                } for p in opt.get("puts", [])],
            }
        return {"error": "No options data for this expiry"}
    except Exception as e:
        return {"error": str(e)}


# --- HTTP Server ---

class ProxyHandler(BaseHTTPRequestHandler):
    """Handle HTTP requests from the web page."""

    def do_GET(self):
        path = self.path
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(path).query))

        action = params.get("action", "")
        ticker = params.get("ticker", "").upper()

        if not ticker and action != "status":
            self._send_json({"error": "Missing 'ticker' parameter"}, 400)
            return

        try:
            if action == "quote":
                result = fetch_yahoo_quote(ticker)
            elif action == "history":
                days = int(params.get("days", 100))
                result = fetch_yahoo_history(ticker, days)
            elif action == "options":
                result = fetch_yahoo_options(ticker)
            elif action == "options-expiry":
                expiry_ts = params.get("expiry_ts", "")
                if not expiry_ts:
                    self._send_json({"error": "Missing 'expiry_ts' parameter"}, 400)
                    return
                result = fetch_yahoo_options_for_expiry(ticker, expiry_ts)
            elif action == "full":
                # Fetch everything at once: quote + history + options
                quote = fetch_yahoo_quote(ticker)
                history = fetch_yahoo_history(ticker, 100)
                options = fetch_yahoo_options(ticker)
                result = {
                    "quote": quote,
                    "history": history,
                    "options": options,
                }
            elif action == "status":
                result = {"status": "ok", "message": "Options proxy is running"}
            else:
                result = {"error": f"Unknown action: {action}. Use: quote, history, options, options-expiry, full, status"}
        except Exception as e:
            result = {"error": str(e)}

        self._send_json(result)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def main():
    port = 8765
    host = "127.0.0.1"
    server = HTTPServer((host, port), ProxyHandler)
    print(f"")
    print(f"  Options Data Proxy Server")
    print(f"  Running at: http://{host}:{port}")
    print(f"  Endpoints:")
    print(f"    /?action=quote&ticker=AAPL        - Stock quote")
    print(f"    /?action=history&ticker=AAPL      - Price history")
    print(f"    /?action=options&ticker=AAPL      - Options chain (all expiries)")
    print(f"    /?action=options-expiry&ticker=AAPL&expiry_ts=xxx  - Options for specific expiry")
    print(f"    /?action=full&ticker=AAPL         - Quote + history + options")
    print(f"    /?action=status                   - Health check")
    print(f"")
    print(f"  Press Ctrl+C to stop.")
    print(f"")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
