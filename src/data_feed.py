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

Two providers: "yfinance" for real Yahoo prices, and "mock" for testing
with no internet. Adding another source later means adding one class
here and nothing else.
"""

import random
import time
from datetime import datetime


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

    def fetch(self, tickers, days_needed):
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

    def fetch(self, tickers, days_needed):
        """
        Fetch in batches. Asking Yahoo for 500 tickers in one request
        tends to time out or get throttled, so we send them in groups
        and stitch the results together.
        """
        batch_size = self.config["data_source"].get("batch_size", 100)
        pause = self.config["data_source"].get("batch_pause_seconds", 1)

        results = []
        skipped = []
        batches = [tickers[i:i + batch_size]
                   for i in range(0, len(tickers), batch_size)]

        for n, batch in enumerate(batches, start=1):
            if len(batches) > 1:
                print(f"  Fetching batch {n} of {len(batches)} "
                      f"({len(batch)} tickers)...")

            got, missed = self._fetch_batch(batch, days_needed)
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


PROVIDERS = {
    "mock": MockProvider,
    "yfinance": YFinanceProvider,
}


def get_provider(config):
    """Pick the provider named in config.yaml."""
    name = config["data_source"]["provider"].lower()
    if name not in PROVIDERS:
        raise DataFeedError(
            f"Unknown provider '{name}'. Valid options: {', '.join(PROVIDERS)}"
        )
    return PROVIDERS[name](config)
