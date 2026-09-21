"""
check_data.py
-------------
Run this when the page is stuck on "Scanning the market".

    python check_data.py

It tests the connection to Yahoo one layer at a time and tells you
exactly which layer is failing, instead of leaving you guessing.
"""

import sys
import time
import traceback

print()
print("=" * 62)
print("  Dip Screener - connection check")
print("=" * 62)
print()


def ok(msg):
    print(f"  PASS  {msg}")


def fail(msg, advice=""):
    print(f"  FAIL  {msg}")
    if advice:
        print()
        for line in advice.strip().splitlines():
            print(f"        {line}")
    print()


# ---------------------------------------------------------------
print("1. Checking the packages are installed")
try:
    import yfinance as yf
    ok(f"yfinance {yf.__version__}")
except ImportError:
    fail("yfinance is not installed",
         "Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    import pandas
    ok(f"pandas {pandas.__version__}")
except ImportError:
    fail("pandas is missing", "Run: pip install -r requirements.txt")
    sys.exit(1)
print()

# ---------------------------------------------------------------
print("2. Fetching a single stock (AAPL)")
start = time.time()
try:
    data = yf.download("AAPL", period="3mo", interval="1d",
                       auto_adjust=True, progress=False, threads=False)
    elapsed = time.time() - start

    if data is None or data.empty:
        fail(f"Yahoo returned nothing after {elapsed:.1f} seconds",
             """This almost always means Yahoo is refusing requests from
             your address. It is usually temporary - wait 15 minutes.
             If you are on a hosted server, Yahoo blocks data centres
             more aggressively than home connections.""")
        sys.exit(1)

    closes = data["Close"].dropna()
    ok(f"got {len(closes)} days in {elapsed:.1f} seconds")
    ok(f"latest close: {float(closes.iloc[-1]):.2f}")
except Exception as e:
    fail(f"Request failed: {e}")
    traceback.print_exc()
    sys.exit(1)
print()

# ---------------------------------------------------------------
print("3. Fetching a batch of 20 (how the screener actually works)")
tickers = ("AAPL MSFT NVDA AMZN GOOGL META TSLA JPM XOM WMT "
           "JNJ V PG MA HD CVX ABBV KO PEP COST")
start = time.time()
try:
    data = yf.download(tickers, period="3mo", interval="1d",
                       auto_adjust=True, group_by="ticker",
                       progress=False, threads=True)
    elapsed = time.time() - start

    if data is None or data.empty:
        fail(f"Batch returned nothing after {elapsed:.1f} seconds",
             """Single stocks work but batches do not. Open config.yaml
             and set  batch_size: 20  and  batch_pause_seconds: 3""")
        sys.exit(1)

    good = 0
    for t in tickers.split():
        try:
            if len(data[t]["Close"].dropna()) > 2:
                good += 1
        except Exception:
            pass

    ok(f"{good} of 20 tickers returned data in {elapsed:.1f} seconds")

    if good < 15:
        fail("Too many gaps - Yahoo is throttling you",
             """Open config.yaml and set:
               batch_size: 25
               batch_pause_seconds: 3
               limit: 50""")
    else:
        rate = elapsed / 20
        projected = rate * 200
        print()
        print(f"  At this speed, 200 stocks takes about "
              f"{projected:.0f} seconds per scan.")
        if projected > 90:
            print("  That is slow. Lower `limit` in config.yaml to 50.")
except Exception as e:
    fail(f"Batch request failed: {e}")
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 62)
print("  Yahoo is reachable and the data looks fine.")
print("  If the web page is still stuck, the problem is the app")
print("  restarting rather than the data. Check the log output.")
print("=" * 62)
print()
