"""
data_feed.py
------------
Gets price data for each ticker.

Every provider returns the SAME shape of data, so the rest of the program
never has to care where the numbers came from:

    {
        "ticker": "AAPL",
        "price": 191.25,        # current / latest price
        "prev_close": 188.10,   # yesterday's closing price
        "history": [...]        # daily closes, oldest first, LAST = today
    }

The last item in "history" is always today's bar, so history[-1] equals
"price" and history[-2] equals "prev_close".

Three providers:
  yfinance - free Yahoo prices, no key, but Yahoo blocks hosted servers
  alpaca   - free API key, works from anywhere including Render
  mock     - fake data for testing with no internet

Adding another source means adding one class here and nothing else.
"""

import json
import random
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from src.net import run_with_deadline, DeadlineExceeded


class DataFeedError(Exception):
    pass


# ----------------------------------------------------------------------
# MOCK PROVIDER - fake but realistic data so we can test with no internet
# ----------------------------------------------------------------------
class MockProvider:
    name = "mock"

    def __init__(self, config):
        self.config = config
        # Seed by the hour so numbers stay stable within a run but change
        # between runs, which makes the 15-minute loop easy to watch.
        random.seed(datetime.now().hour)

    def fetch(self, tickers, days_needed, progress_cb=None):
        results = []
        for t in tickers:
            base = random.uniform(40, 400)
            history = []
            price = base
            for _ in range(days_needed):
                price *= 1 + random.uniform(-0.02, 0.021)
                history.append(round(price, 2))

            # Today's bar is appended to history, not held apart from it.
            current = round(history[-1] * (1 + random.uniform(-0.06, 0.03)), 2)
            history.append(current)

            results.append({
                "ticker": t,
                "price": current,
                "prev_close": history[-2],
                "history": history,
            })
        return results


# ----------------------------------------------------------------------
# REAL PROVIDERS - placeholders, wired up in Step 2
# ----------------------------------------------------------------------
class YFinanceProvider:
    """
    Live daily prices from Yahoo Finance. No API key needed.

    Yahoo's free data is delayed roughly 15 minutes, which lines up well
    with our 15-minute refresh. It is fine for screening, not for trading
    to the second.
    """
    name = "yfinance"

    def __init__(self, config):
        self.config = config
        try:
            import yfinance
        except ImportError:
            raise DataFeedError(
                "The yfinance package is not installed.\n"
                "  Run:  pip install -r requirements.txt"
            )
        self._yf = yfinance

    @staticmethod
    def _period_for(days_needed):
        """
        Yahoo wants a period like '6mo', not a number of days.
        Markets are open ~21 days a month, so we convert and round up.
        """
        months = (days_needed / 21) + 1
        for label, size in [("3mo", 3), ("6mo", 6), ("1y", 12),
                            ("2y", 24), ("5y", 60)]:
            if months <= size:
                return label
        return "max"

    def fetch(self, tickers, days_needed, progress_cb=None):
        """
        Fetch in batches. Asking Yahoo for 500 tickers in one request
        tends to time out or get throttled, so we send them in groups
        and stitch the results together.

        progress_cb, if given, is called with a short status string so
        the web page can show what is happening.
        """
        batch_size = self.config["data_source"].get("batch_size", 100)
        pause = self.config["data_source"].get("batch_pause_seconds", 1)

        results = []
        skipped = []
        batches = [tickers[i:i + batch_size]
                   for i in range(0, len(tickers), batch_size)]

        for n, batch in enumerate(batches, start=1):
            note = f"Fetching batch {n} of {len(batches)}"
            print(f"  {note} ({len(batch)} tickers)...")
            if progress_cb:
                progress_cb(f"{note} - {len(results)} stocks so far")

            started = time.time()
            got, missed = self._fetch_batch(batch, days_needed)
            took = time.time() - started
            print(f"    got {len(got)}, missed {len(missed)} "
                  f"in {took:.1f}s")
            results.extend(got)
            skipped.extend(missed)

            if n < len(batches) and pause:
                time.sleep(pause)

        if skipped:
            preview = ", ".join(skipped[:8])
            more = f" and {len(skipped) - 8} more" if len(skipped) > 8 else ""
            print(f"  Note: no usable data for {preview}{more}")

        if not results:
            raise DataFeedError(
                "No tickers returned usable data. Check your internet "
                "connection and the tickers in config.yaml."
            )

        return results

    def _fetch_batch(self, tickers, days_needed):
        """Fetch one group of tickers. Returns (results, skipped)."""
        period = self._period_for(days_needed)

        try:
            data = self._yf.download(
                tickers=" ".join(tickers),
                period=period,
                interval="1d",
                auto_adjust=True,     # adjusts for splits and dividends
                group_by="ticker",
                progress=False,
                threads=True,
            )
        except Exception as e:
            print(f"  Batch failed ({e}); skipping it this cycle.")
            return [], list(tickers)

        if data is None or data.empty:
            return [], list(tickers)

        results = []
        skipped = []

        for t in tickers:
            try:
                # With one ticker, columns are flat; with several they are nested.
                frame = data[t] if len(tickers) > 1 else data
                closes = frame["Close"].dropna().tolist()
            except (KeyError, TypeError):
                skipped.append(t)
                continue

            if len(closes) < 2:
                skipped.append(t)
                continue

            # The final bar is today, still moving while markets are open.
            # We keep it in history so the moving averages react to today.
            history = [round(float(c), 2) for c in closes]
            current = history[-1]

            results.append({
                "ticker": t,
                "price": current,
                "prev_close": history[-2],
                "history": history,
            })

        return results, skipped


# ----------------------------------------------------------------------
# ALPACA - a proper API with a key. Works from hosted servers, which is
# why it exists here: Yahoo blocks data centres, Alpaca does not.
# ----------------------------------------------------------------------
class AlpacaProvider:
    """
    Free Alpaca account, no funding needed. Two things make it a good fit:
    one request can carry a hundred symbols, and the free plan allows 200
    requests a minute.

    The free plan's prices come from the IEX exchange rather than every
    exchange combined. For big S&P 500 companies the difference is small,
    usually a cent or two. It is the trade for free real-time data.
    """
    name = "alpaca"
    BASE = "https://data.alpaca.markets/v2/stocks/bars"

    # Guard rails. Without these a stuck request or a repeating page
    # token leaves the scan running silently for ever, which shows up as
    # a page that says "Scanning" and never changes.
    REQUEST_TIMEOUT = 20      # per request
    BATCH_DEADLINE = 90       # for all pages of one batch combined
    MAX_PAGES = 25

    def __init__(self, config):
        ds = config["data_source"]
        self.config = config
        self.key = ds.get("api_key", "")
        self.secret = ds.get("api_secret", "")
        self.feed = ds.get("feed", "iex")

        if not self.key or not self.secret:
            raise DataFeedError(
                "Alpaca needs both an api_key and an api_secret.\n"
                "  Get them free at https://alpaca.markets - no funding needed.\n"
                "  On a host, set ALPACA_API_KEY and ALPACA_API_SECRET."
            )

    @staticmethod
    def to_alpaca(symbol):
        """Alpaca writes share classes with a dot: BRK-B becomes BRK.B."""
        return symbol.replace("-", ".")

    def _request(self, params):
        url = f"{self.BASE}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={
            "APCA-API-KEY-ID": self.key,
            "APCA-API-SECRET-KEY": self.secret,
            "accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=self.REQUEST_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            if e.code == 401:
                raise DataFeedError(
                    "Alpaca rejected your key. Check api_key and api_secret, "
                    "and that both came from the same generated pair."
                )
            if e.code == 403:
                raise DataFeedError(
                    f"Alpaca refused the '{self.feed}' feed for this account.\n"
                    "  The sip feed needs a paid data plan. If this key is on\n"
                    "  the free plan, set feed: \"iex\" in config.yaml.\n"
                    "  Note a paper account does not always carry the same\n"
                    "  data subscription as the live account it sits under."
                )
            if e.code == 429:
                raise DataFeedError(
                    "Alpaca rate limit hit. Raise batch_pause_seconds in "
                    "config.yaml."
                )
            raise DataFeedError(f"Alpaca error {e.code}: {body}")
        except urllib.error.URLError as e:
            raise DataFeedError(
                f"No response from Alpaca within {self.REQUEST_TIMEOUT}s: "
                f"{e.reason}"
            )
        except socket.timeout:
            raise DataFeedError(
                f"Alpaca did not respond within {self.REQUEST_TIMEOUT}s."
            )

    def _fetch_batch(self, tickers, days_needed):
        """Fetch one group of symbols, following pagination to the end."""
        # Markets are open about 21 days a month, so ask for more calendar
        # days than trading days, plus a margin for holidays.
        calendar_days = int(days_needed * 1.5) + 14
        start = (datetime.now() - timedelta(days=calendar_days)).strftime("%Y-%m-%d")

        symbols = [self.to_alpaca(t) for t in tickers]
        collected = {}
        page_token = None
        page = 0
        deadline = time.time() + self.BATCH_DEADLINE

        while True:
            page += 1
            if page > self.MAX_PAGES:
                print(f"    stopping after {self.MAX_PAGES} pages - "
                      "using what we have", flush=True)
                break
            if time.time() > deadline:
                print(f"    stopping after {self.BATCH_DEADLINE}s - "
                      "using what we have", flush=True)
                break

            params = {
                "symbols": ",".join(symbols),
                "timeframe": "1Day",
                "start": start,
                "limit": 10000,
                "adjustment": "all",      # corrects for splits and dividends
                "feed": self.feed,
                "sort": "asc",
            }
            if page_token:
                params["page_token"] = page_token

            started = time.time()
            payload = self._request(params)
            returned = sum(len(v) for v in (payload.get("bars") or {}).values())
            print(f"    page {page}: {returned} bars in "
                  f"{time.time() - started:.1f}s", flush=True)

            for symbol, bars in (payload.get("bars") or {}).items():
                collected.setdefault(symbol, []).extend(bars)

            new_token = payload.get("next_page_token")
            # A token identical to the one we just used would loop for ever.
            if not new_token or new_token == page_token:
                break
            page_token = new_token

        results = []
        skipped = []

        for original in tickers:
            bars = collected.get(self.to_alpaca(original), [])
            closes = [round(float(b["c"]), 2) for b in bars if b.get("c")]

            if len(closes) < 2:
                skipped.append(original)
                continue

            results.append({
                "ticker": original,
                "price": closes[-1],
                "prev_close": closes[-2],
                "history": closes,
            })

        return results, skipped

    def fetch(self, tickers, days_needed, progress_cb=None):
        batch_size = self.config["data_source"].get("batch_size", 100)
        pause = self.config["data_source"].get("batch_pause_seconds", 1)

        results = []
        skipped = []
        batches = [tickers[i:i + batch_size]
                   for i in range(0, len(tickers), batch_size)]

        for n, batch in enumerate(batches, start=1):
            note = f"Fetching batch {n} of {len(batches)}"
            print(f"  {note} ({len(batch)} symbols)...", flush=True)
            if progress_cb:
                progress_cb(f"{note} - {len(results)} stocks so far")

            started = time.time()
            try:
                # A hard limit that holds even if the request is stuck in
                # a DNS lookup, which no socket timeout can interrupt.
                got, missed = run_with_deadline(
                    self.BATCH_DEADLINE, self._fetch_batch, batch, days_needed)
            except DeadlineExceeded:
                raise DataFeedError(
                    f"Alpaca did not answer within {self.BATCH_DEADLINE}s. "
                    "The server's network may be the problem rather than "
                    "your key - open /net on this site to check."
                )
            results.extend(got)
            skipped.extend(missed)
            print(f"    got {len(got)}, missed {len(missed)} "
                  f"in {time.time() - started:.1f}s", flush=True)

            if n < len(batches) and pause:
                time.sleep(pause)

        if skipped:
            preview = ", ".join(skipped[:8])
            more = f" and {len(skipped) - 8} more" if len(skipped) > 8 else ""
            print(f"  Note: no data for {preview}{more}", flush=True)

        if not results:
            raise DataFeedError(
                "Alpaca returned no usable data for any symbol. Check that "
                "your key is active and your tickers are US-listed."
            )

        return results


PROVIDERS = {
    "mock": MockProvider,
    "yfinance": YFinanceProvider,
    "alpaca": AlpacaProvider,
}


def get_provider(config):
    """Pick the provider named in config.yaml."""
    name = config["data_source"]["provider"].lower()
    if name not in PROVIDERS:
        raise DataFeedError(
            f"Unknown provider '{name}'. Valid options: {', '.join(PROVIDERS)}"
        )
    return PROVIDERS[name](config)
