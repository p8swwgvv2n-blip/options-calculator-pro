#!/usr/bin/env python3
"""
Options Lab 本地数据代理 v2.1
==============================
双击运行，在 http://127.0.0.1:8765 启动本地代理服务器。
网页会自动检测并连接此代理，实时获取期权 IV 数据。

功能：
  - 从 Yahoo Finance 获取实时期权链（含 IV）
  - 获取股票报价和历史数据
  - 支持 SOCKS5 代理（VPN/SS/SSR 等）
  - 仅监听 127.0.0.1，数据不出本机

用法：
  方式① 直接双击（使用系统代理或不使用代理）
  方式② 终端运行并指定代理：
    python3 options-proxy-server.py --proxy socks5h://127.0.0.1:1080
    python3 options-proxy-server.py --proxy http://127.0.0.1:7890
  方式③ 交互模式（启动时询问代理地址）：
    python3 options-proxy-server.py --ask
"""

import json
import sys
import os
import socket
import struct
import urllib.request
import urllib.parse
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

PORT = 8765
HOST = "127.0.0.1"

# ─── SOCKS5 Support ───

SOCKS_PROXY = None  # Set to ("host", port) for SOCKS5


class Socks5SocketWrapper:
    """Wrap a socket to route through SOCKS5 proxy."""

    def __init__(self, proxy_host, proxy_port):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self._sock = None

    def connect_via_socks5(self, dest_host, dest_port):
        """Establish connection through SOCKS5 proxy."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(15)
        self._sock.connect((self.proxy_host, self.proxy_port))

        # SOCKS5 handshake: no auth
        self._sock.sendall(b'\x05\x01\x00')
        resp = self._sock.recv(2)
        if resp[0:2] != b'\x05\x00':
            raise ConnectionError("SOCKS5 auth failed")

        # SOCKS5 connect request (domain name)
        dest_bytes = dest_host.encode('utf-8')
        port_bytes = struct.pack('>H', dest_port)
        request = b'\x05\x01\x00\x03' + bytes([len(dest_bytes)]) + dest_bytes + port_bytes
        self._sock.sendall(request)

        resp = self._sock.recv(10)
        if len(resp) < 2 or resp[1] != 0x00:
            raise ConnectionError(f"SOCKS5 connect failed: {resp[1] if len(resp) > 1 else 'no response'}")

        # Read remaining bind address if needed
        if len(resp) >= 4:
            atyp = resp[3]
            if atyp == 0x01:  # IPv4
                remaining = 4 + 2 - (len(resp) - 4)
            elif atyp == 0x03:  # Domain
                remaining = 1 + resp[4] + 2 - (len(resp) - 4)
            elif atyp == 0x04:  # IPv6
                remaining = 16 + 2 - (len(resp) - 4)
            else:
                remaining = 0
            if remaining > 0:
                self._sock.recv(remaining)

        return self._sock

    def make_connection(self, url):
        """Create a SOCKS5 connection for urllib."""
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        return self.connect_via_socks5(host, port)


class Socks5HTTPHandler(urllib.request.HTTPHandler):
    """Custom HTTP handler that routes through SOCKS5."""
    def __init__(self, proxy_host, proxy_port):
        super().__init__()
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port

    def http_open(self, req):
        return self._open(req)

    def _open(self, req):
        import http.client
        parsed = urllib.parse.urlparse(req.full_url)
        wrapper = Socks5SocketWrapper(self.proxy_host, self.proxy_port)
        sock = wrapper.connect_via_socks5(parsed.hostname, parsed.port or 80)

        class SocksHTTPConnection(http.client.HTTPConnection):
            def connect(self):
                self.sock = sock
        conn = SocksHTTPConnection(parsed.hostname, parsed.port or 80)
        conn.sock = sock
        return conn


class Socks5HTTPSHandler(urllib.request.HTTPSHandler):
    """Custom HTTPS handler that routes through SOCKS5."""
    import ssl
    def __init__(self, proxy_host, proxy_port):
        super().__init__()
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port

    def https_open(self, req):
        import http.client
        import ssl as _ssl
        parsed = urllib.parse.urlparse(req.full_url)
        wrapper = Socks5SocketWrapper(self.proxy_host, self.proxy_port)
        sock = wrapper.connect_via_socks5(parsed.hostname, parsed.port or 443)

        context = _ssl.create_default_context()
        wrapped = context.wrap_socket(sock, server_hostname=parsed.hostname)

        class SocksHTTPSConnection(http.client.HTTPSConnection):
            def connect(self):
                self.sock = wrapped
        conn = SocksHTTPSConnection(parsed.hostname, parsed.port or 443)
        conn.sock = wrapped
        return conn


def _build_opener():
    """Build a urllib opener, optionally with SOCKS5 proxy."""
    if SOCKS_PROXY:
        host, port = SOCKS_PROXY
        handlers = [
            Socks5HTTPHandler(host, port),
            Socks5HTTPSHandler(host, port),
        ]
        return urllib.request.build_opener(*handlers)
    return urllib.request.build_opener()


# ─── Yahoo Finance Data Fetching ───

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def _yahoo_get(url, timeout=15):
    """Make a GET request to Yahoo Finance, optionally via SOCKS5."""
    opener = _build_opener()
    req = urllib.request.Request(url, headers=HEADERS)
    with opener.open(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def fetch_yahoo_quote(ticker):
    """Fetch real-time stock quote."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}?interval=1d&range=5d"
    data = _yahoo_get(url)
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


def fetch_yahoo_history(ticker, days=100):
    """Fetch daily OHLC history."""
    range_map = {30: "1mo", 60: "2mo", 100: "3mo", 250: "1y"}
    best = min(range_map.keys(), key=lambda k: abs(k - days))
    range_str = range_map[best]
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}?interval=1d&range={range_str}"
    data = _yahoo_get(url)
    result = data["chart"]["result"][0]
    ts_list = result["timestamp"]
    q = result["indicators"]["quote"][0]
    history = []
    for i in range(len(ts_list)):
        history.append({
            "date": datetime.utcfromtimestamp(ts_list[i]).strftime("%Y-%m-%d"),
            "open": (q.get("open") or [None]*len(ts_list))[i],
            "high": (q.get("high") or [None]*len(ts_list))[i],
            "low": (q.get("low") or [None]*len(ts_list))[i],
            "close": (q.get("close") or [None]*len(ts_list))[i],
            "volume": (q.get("volume") or [None]*len(ts_list))[i],
        })
    return {"symbol": ticker.upper(), "history": history}


def _clean_option(opt):
    return {
        "strike": opt["strike"],
        "lastPrice": opt.get("lastPrice"),
        "bid": opt.get("bid"),
        "ask": opt.get("ask"),
        "volume": opt.get("volume"),
        "openInterest": opt.get("openInterest"),
        "impliedVolatility": opt.get("impliedVolatility"),
        "delta": opt.get("delta"),
        "gamma": opt.get("gamma"),
        "theta": opt.get("theta"),
        "vega": opt.get("vega"),
        "inTheMoney": opt.get("inTheMoney"),
    }


def fetch_yahoo_options(ticker):
    """Fetch all options chain (first expiry + expiry list)."""
    url = f"https://query2.finance.yahoo.com/v7/finance/options/{ticker.upper()}"
    data = _yahoo_get(url)
    result = data["optionChain"]["result"][0]
    expirations = result.get("expirationDates", [])
    options = result.get("options", [])
    chain = {}
    for opt in options:
        exp_date = opt.get("expirationDate")
        chain[exp_date] = {
            "calls": [_clean_option(c) for c in opt.get("calls", [])],
            "puts": [_clean_option(p) for p in opt.get("puts", [])],
        }
    return {
        "symbol": result.get("quote", {}).get("symbol", ticker.upper()),
        "expirationDates": expirations,
        "chains": chain,
    }


def fetch_yahoo_options_for_expiry(ticker, expiry_ts):
    """Fetch options chain for a specific expiry date."""
    url = f"https://query2.finance.yahoo.com/v7/finance/options/{ticker.upper()}?date={expiry_ts}"
    data = _yahoo_get(url)
    result = data["optionChain"]["result"][0]
    options = result.get("options", [])
    if options:
        opt = options[0]
        return {
            "calls": [_clean_option(c) for c in opt.get("calls", [])],
            "puts": [_clean_option(p) for p in opt.get("puts", [])],
        }
    return {"error": "No options data for this expiry"}


# ─── HTTP Server ───

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(path).query))
        action = params.get("action", "")
        ticker = params.get("ticker", "").upper()

        if action == "status":
            self._send_json({
                "status": "ok",
                "version": "2.1",
                "proxy": f"{SOCKS_PROXY[0]}:{SOCKS_PROXY[1]}" if SOCKS_PROXY else "direct",
                "time": datetime.now().isoformat(),
            })
            return

        if not ticker:
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
                quote = fetch_yahoo_quote(ticker)
                history = fetch_yahoo_history(ticker, 100)
                options = fetch_yahoo_options(ticker)
                result = {"quote": quote, "history": history, "options": options}
            else:
                result = {"error": f"Unknown action: {action}"}
        except Exception as e:
            result = {"error": str(e)}

        self._send_json(result)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_HEAD(self):
        """Handle HEAD requests (used by some health check tools)."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        msg = args[0] if args else ""
        ts = datetime.now().strftime('%H:%M:%S')
        if "error" in str(args).lower():
            print(f"  ERR  [{ts}] {msg}")
        else:
            print(f"  >>>  [{ts}] {msg}")


# ─── Startup ───

def parse_proxy_arg(proxy_str):
    """Parse proxy string like socks5h://127.0.0.1:1080 or http://127.0.0.1:7890."""
    if not proxy_str:
        return None
    proxy_str = proxy_str.strip()
    # Remove protocol prefix
    for prefix in ["socks5h://", "socks5://", "socks://", "http://", "https://"]:
        if proxy_str.startswith(prefix):
            proxy_str = proxy_str[len(prefix):]
            break
    parts = proxy_str.split(":")
    if len(parts) == 2:
        return (parts[0], int(parts[1]))
    return None


def ask_proxy():
    """Interactive mode: ask user for proxy address."""
    print("")
    print("  Options Lab 本地数据代理 v2.1")
    print("  " + "=" * 44)
    print("")
    print("  Yahoo Finance 在中国大陆无法直接访问。")
    print("  如果你本机有 VPN / SS / SSR / Clash 等代理，")
    print("  请输入代理地址（直接回车则不使用代理）：")
    print("")
    print("  常见代理地址：")
    print("    Clash:    socks5://127.0.0.1:7890")
    print("    SS/SSR:   socks5://127.0.0.1:1080")
    print("    V2Ray:    socks5://127.0.0.1:10808")
    print("    系统代理:  http://127.0.0.1:7890")
    print("")
    try:
        answer = input("  请输入代理地址 → ").strip()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer:
        return parse_proxy_arg(answer)
    return None


def open_browser():
    import time
    time.sleep(1.5)
    try:
        webbrowser.open(f"http://{HOST}:{PORT}/?action=status")
    except Exception:
        pass


def test_yahoo_connection():
    """Quick test to verify Yahoo Finance is accessible."""
    try:
        data = fetch_yahoo_quote("AAPL")
        if data.get("price"):
            print(f"  ✓ Yahoo Finance 连接正常！AAPL 当前价格: ${data['price']}")
            return True
        else:
            print(f"  ✗ Yahoo 返回了无效数据: {data}")
            return False
    except Exception as e:
        print(f"  ✗ Yahoo Finance 连接失败: {e}")
        print("")
        if SOCKS_PROXY:
            print("  请检查代理地址是否正确，代理软件是否已启动。")
        else:
            print("  如果你在大陆，需要使用代理才能访问 Yahoo Finance。")
            print("  请用 --proxy 参数指定代理地址，例如：")
            print("    python3 options-proxy-server.py --proxy socks5://127.0.0.1:7890")
        return False


def main():
    global SOCKS_PROXY

    # Parse command-line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Options Lab 本地数据代理")
    parser.add_argument("--proxy", type=str, help="代理地址，如 socks5://127.0.0.1:7890")
    parser.add_argument("--ask", action="store_true", help="启动时交互询问代理地址")
    parser.add_argument("--port", type=int, default=PORT, help=f"监听端口（默认 {PORT}）")
    args = parser.parse_args()

    port = args.port

    # Determine proxy
    if args.ask:
        SOCKS_PROXY = ask_proxy()
    elif args.proxy:
        SOCKS_PROXY = parse_proxy_arg(args.proxy)
        if not SOCKS_PROXY:
            print(f"  无法解析代理地址: {args.proxy}")
            print("  格式: socks5://host:port 或 http://host:port")
            sys.exit(1)

    # Test connection
    print("")
    print("=" * 52)
    print("   Options Lab 本地数据代理 v2.1")
    print("=" * 52)
    print("")
    if SOCKS_PROXY:
        print(f"   代理模式:  {SOCKS_PROXY[0]}:{SOCKS_PROXY[1]}")
    else:
        print(f"   代理模式:  直连（无代理）")
    print(f"   服务地址:  http://{HOST}:{port}")
    print("")
    print("   正在测试 Yahoo Finance 连接…")
    yahoo_ok = test_yahoo_connection()
    print("")

    if not yahoo_ok and not SOCKS_PROXY:
        print("  " + "-" * 44)
        print("  提示：不使用代理的话，期权数据将无法获取。")
        print("  股票报价仍可通过 Twelve Data / Alpha Vantage 获取。")
        print("  " + "-" * 44)
        print("")

    print(f"   接口列表:")
    print(f"     报价:      /?action=quote&ticker=AAPL")
    print(f"     历史K线:   /?action=history&ticker=AAPL")
    print(f"     期权链:    /?action=options&ticker=AAPL")
    print(f"     指定到期:  /?action=options-expiry&ticker=AAPL&expiry_ts=xxx")
    print(f"     全部数据:  /?action=full&ticker=AAPL")
    print(f"     健康检查:  /?action=status")
    print("")
    print("   使用方式：")
    print("   1. 保持此窗口运行（不要关闭）")
    print("   2. 打开 Options Lab 网页")
    print("   3. 网页会自动检测代理并获取实时期权 IV")
    print("")
    print("   按 Ctrl+C 停止服务")
    print("-" * 52)

    # Start server
    server = HTTPServer((HOST, port), ProxyHandler)
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n   代理已停止。\n")
        server.server_close()


if __name__ == "__main__":
    main()
