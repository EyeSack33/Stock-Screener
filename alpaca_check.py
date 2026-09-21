"""
alpaca_check.py
---------------
Works out why an Alpaca key is being rejected, and returns the answer as
a list of plain text lines.

The same code backs two things: the /debug page in your browser, and
check_alpaca.py on your own computer. Keeping one copy means the two can
never drift apart and give different answers.

It never prints the key itself, only its first two characters and its
length, so it is safe to view on a public page.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

DATA_URL = "https://data.alpaca.markets/v2/stocks/bars"
PAPER_ACCOUNT_URL = "https://paper-api.alpaca.markets/v2/account"
LIVE_ACCOUNT_URL = "https://api.alpaca.markets/v2/account"


# Kept short on purpose. This runs inside a web request, and four calls
# at a long timeout would outlast the host's proxy and hang the page.
TIMEOUT_SECONDS = 6


def _call(url, key, secret, params=None):
    """Returns (status_code, body_text). status is None if unreachable."""
    from src.net import http_get_isolated
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return http_get_isolated(url, headers={
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "accept": "application/json",
    }, timeout=TIMEOUT_SECONDS)


def run(key, secret):
    """The full diagnostic. Returns a list of lines to print or display."""
    out = []

    if not key or not secret:
        out.append("No key or secret found.")
        out.append("")
        out.append("On Render: open the service, click Environment, and")
        out.append("check ALPACA_API_KEY and ALPACA_API_SECRET are both set.")
        return out

    # ---- What we were handed ----
    out.append("THE CREDENTIALS")
    out.append("-" * 54)
    prefix = key[:2].upper()
    if prefix == "PK":
        out.append("  Key prefix PK - this is a PAPER key")
    elif prefix == "AK":
        out.append("  Key prefix AK - this is a LIVE key")
    else:
        out.append(f"  Key prefix '{key[:2]}' - neither PK (paper) nor AK")
        out.append("  (live). You may have pasted the wrong value.")

    out.append(f"  Key length {len(key)}, secret length {len(secret)}")

    if key != key.strip() or secret != secret.strip():
        out.append("  >> STRAY SPACES FOUND. This alone causes a 401.")
        out.append("     Re-paste both values with no leading or")
        out.append("     trailing whitespace.")
    key, secret = key.strip(), secret.strip()
    out.append("")

    # ---- Is the key valid at all? ----
    out.append("TEST 1 - TRADING ENDPOINTS (is the key valid at all?)")
    out.append("-" * 54)
    valid_somewhere = False
    all_timed_out = True
    for label, url in [("paper", PAPER_ACCOUNT_URL), ("live", LIVE_ACCOUNT_URL)]:
        status, body = _call(url, key, secret)
        if status is not None:
            all_timed_out = False
        if status == 200:
            valid_somewhere = True
            try:
                info = json.loads(body)
                out.append(f"  {label:<6} OK - account status "
                           f"{info.get('status', '?')}")
            except Exception:
                out.append(f"  {label:<6} OK")
        elif status is None:
            out.append(f"  {label:<6} no response - {body}")
        else:
            out.append(f"  {label:<6} {status}")

    if not valid_somewhere and all_timed_out:
        out.append("")
        out.append("  VERDICT: no response from Alpaca at all, rather than")
        out.append("  a rejection. Something is blocking outbound requests")
        out.append("  from this server, so the key is not the problem.")
        return out

    if not valid_somewhere:
        out.append("")
        out.append("  VERDICT: the key fails on both trading endpoints, so")
        out.append("  the credentials themselves are wrong. Market data is")
        out.append("  not the problem.")
        out.append("")
        out.append("  Almost always this means the Key ID and the Secret")
        out.append("  came from different generated pairs. Generate a fresh")
        out.append("  pair and copy BOTH from the same screen at the same")
        out.append("  time, then update both values in Render.")
        return out
    out.append("")

    # ---- Does market data work? ----
    out.append("TEST 2 - MARKET DATA (what the screener uses)")
    out.append("-" * 54)
    results = {}
    for feed in ("iex", "sip"):
        status, body = _call(DATA_URL, key, secret, {
            "symbols": "AAPL",
            "timeframe": "1Day",
            "start": "2026-08-01",
            "limit": 5,
            "feed": feed,
        })
        results[feed] = status

        if status == 200:
            try:
                bars = json.loads(body).get("bars", {}).get("AAPL", [])
                last = bars[-1]["c"] if bars else "?"
                out.append(f"  {feed:<4} OK - {len(bars)} bars, "
                           f"latest close {last}")
            except Exception:
                out.append(f"  {feed:<4} OK but response was unexpected")
        else:
            snippet = " ".join(body.split())[:100]
            out.append(f"  {feed:<4} {status} - {snippet}")
            if status == 401 and "<html" in body.lower():
                out.append("       (raw HTML 401, not Alpaca JSON - this is")
                out.append("        the known data-endpoint fault)")
    out.append("")

    # ---- What to do ----
    out.append("VERDICT")
    out.append("-" * 54)
    if results.get("iex") == 200:
        out.append("  Your key works for market data.")
        out.append("")
        out.append("  Set  feed: \"iex\"  in config.yaml and commit it.")
        if results.get("sip") == 200:
            out.append("  sip works too, so either value is fine.")
        else:
            out.append("  sip is not available on this account, which is")
            out.append("  normal on the free plan.")
    elif results.get("iex") == 403:
        out.append("  The key is valid but market data is not enabled on")
        out.append("  this account. This usually means the account signup")
        out.append("  was never fully completed - open the Alpaca dashboard")
        out.append("  and finish any outstanding application steps.")
    else:
        out.append("  The key works for trading but not for market data.")
        out.append("  Nothing in config.yaml will fix that.")
        out.append("")
        out.append("  Contact Alpaca support quoting the status codes")
        out.append("  above, or use a different Alpaca account.")

    return out
