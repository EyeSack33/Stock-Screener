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

    # Invisible characters (zero-width spaces, non-breaking spaces, line
    # breaks in the middle) survive copy and paste and break the key while
    # looking completely normal on screen.
    for label, value in (("Key", key), ("Secret", secret)):
        odd = [(i, ch) for i, ch in enumerate(value) if not ch.isalnum()]
        if odd:
            where = ", ".join(f"position {i + 1} ({repr(ch)[1:-1] or 'blank'})"
                              for i, ch in odd[:5])
            out.append(f"  >> {label} contains {len(odd)} character(s) that are")
            out.append(f"     not letters or digits: {where}")
            out.append("     Delete the value in Render and type or paste it")
            out.append("     again, checking nothing extra comes with it.")
        else:
            out.append(f"  {label}: letters and digits only - no hidden characters")

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

    if not valid_somewhere:
        out.append("")
        out.append("  The trading endpoints refused this key. That does NOT")
        out.append("  settle it: a key can be limited to market data, and")
        out.append("  the screener never uses trading. Testing data next.")
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
    iex, sip = results.get("iex"), results.get("sip")
    if iex == 200:
        out.append("  Your key WORKS for market data, which is all the")
        out.append("  screener needs. Use  feed: \"iex\".")
        if not valid_somewhere:
            out.append("")
            out.append("  (The trading refusals above are irrelevant here -")
            out.append("   this key is probably limited to data, or trading")
            out.append("   is not enabled on the account.)")
    elif iex == 401 and not valid_somewhere:
        out.append("  Refused everywhere, data included. Alpaca does not")
        out.append("  accept this key and secret together. Either the")
        out.append("  secret is incomplete, or the pair was replaced or")
        out.append("  revoked after it was copied.")
    elif iex == 403:
        out.append("  The key is recognised but market data is not enabled")
        out.append("  for this account. Check the Alpaca dashboard for any")
        out.append("  unfinished signup or data-agreement steps.")
    elif iex is None:
        out.append("  No answer from the data endpoint at all, while the")
        out.append("  trading endpoints did answer. That points at the")
        out.append("  data service specifically, not your key.")
    else:
        out.append(f"  Unexpected result from the data endpoint ({iex}).")
        out.append("  The detail beside it above is the best clue.")
    return out
