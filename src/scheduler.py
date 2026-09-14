"""
scheduler.py
------------
Runs one scan every `refresh_minutes` in the background and holds the
result in memory.

Why this exists: if the web page fetched fresh prices every time you
loaded it, hitting refresh ten times would mean ten calls to Yahoo and
a quick rate-limit block. Instead, one background worker updates the
data on schedule, and every page view reads the stored copy.
"""

import threading
import time
import traceback
from datetime import datetime

from src import indicators, scoring, market_hours, universe
from src.data_feed import get_provider, DataFeedError
from src.universe import UniverseError


class ScreenerState:
    """The shared, thread-safe store of the latest results."""

    def __init__(self):
        self.lock = threading.Lock()
        self.rows = []              # stocks that passed the threshold
        self.scanned = 0            # how many were checked
        self.last_updated = None
        self.last_error = None
        self.is_refreshing = False

    def snapshot(self):
        """Read the current data safely while the worker may be writing."""
        with self.lock:
            return {
                "rows": list(self.rows),
                "scanned": self.scanned,
                "last_updated": self.last_updated,
                "last_error": self.last_error,
                "is_refreshing": self.is_refreshing,
            }


def run_scan(config):
    """One full cycle: fetch -> calculate -> score. Returns (top, total)."""
    provider = get_provider(config)
    days_needed = config["indicators"]["long_ma_days"] + 10
    tickers = universe.resolve(config)

    quotes = provider.fetch(tickers, days_needed)
    rows = indicators.compute_all(quotes, config)
    top, all_scored = scoring.rank(rows, config)
    return top, all_scored


def refresh(state, config):
    """Run a scan and store the outcome, recording any error instead of crashing."""
    with state.lock:
        state.is_refreshing = True

    try:
        top, all_scored = run_scan(config)

        with state.lock:
            state.rows = top
            state.scanned = len(all_scored)
            state.last_updated = datetime.now()
            state.last_error = None
        print(f"  [{datetime.now():%H:%M:%S}] Updated - "
              f"{len(top)} of {len(all_scored)} passed")

    except (DataFeedError, UniverseError, NotImplementedError) as e:
        with state.lock:
            state.last_error = str(e)
        print(f"  [{datetime.now():%H:%M:%S}] Data error: {e}")

    except Exception as e:                      # anything unexpected
        with state.lock:
            state.last_error = f"Unexpected error: {e}"
        print(f"  [{datetime.now():%H:%M:%S}] Unexpected error:")
        traceback.print_exc()

    finally:
        with state.lock:
            state.is_refreshing = False


def start_background_worker(state, config):
    """
    Launch the repeating refresh loop on its own thread so the web
    server stays responsive while prices are being fetched.
    """
    minutes = config["schedule"]["refresh_minutes"]

    def loop():
        # Scan immediately so the page is not empty on first load.
        refresh(state, config)

        while True:
            time.sleep(minutes * 60)

            if market_hours.is_market_open(config):
                refresh(state, config)
            else:
                print(f"  [{datetime.now():%H:%M:%S}] Market closed - skipping")

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread
