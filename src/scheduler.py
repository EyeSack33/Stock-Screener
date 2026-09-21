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

import os
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
        self.progress = ""            # what the scan is doing right now
        self.scan_started = None      # when the current scan began
        self.worker_pid = None        # which process the scan thread lives in

    def snapshot(self):
        """Read the current data safely while the worker may be writing."""
        with self.lock:
            return {
                "rows": list(self.rows),
                "scanned": self.scanned,
                "last_updated": self.last_updated,
                "last_error": self.last_error,
                "is_refreshing": self.is_refreshing,
                "progress": self.progress,
                "scan_started": self.scan_started,
            }


def run_scan(config, progress_cb=None):
    """One full cycle: fetch -> calculate -> score. Returns (top, total)."""
    def step(message):
        print(f"  {message}", flush=True)
        if progress_cb:
            progress_cb(message)

    name = config["data_source"]["provider"]
    step(f"Loading the {name} provider")
    provider = get_provider(config)

    step("Reading the stock list")
    days_needed = config["indicators"]["long_ma_days"] + 10
    tickers = universe.resolve(config)

    if progress_cb:
        progress_cb(f"Starting - {len(tickers)} stocks to check")

    quotes = provider.fetch(tickers, days_needed, progress_cb=progress_cb)

    rows = indicators.compute_all(quotes, config)

    if config["scoring"].get("mode", "dip").lower() == "analyst":
        step("Finding stocks that dropped")
        dipped = scoring.dip_candidates(rows, config)
        step(f"{len(dipped)} dropped - fetching analyst ratings")
        from src import ratings
        ratings.attach(dipped, config, progress_cb=progress_cb)
        return scoring.rank_by_analysts(dipped, config), rows

    if progress_cb:
        progress_cb("Calculating scores")
    top, all_scored = scoring.rank(rows, config)
    return top, all_scored


def refresh(state, config):
    """Run a scan and store the outcome, recording any error instead of crashing."""
    with state.lock:
        state.is_refreshing = True
        state.scan_started = datetime.now()
        state.progress = "Starting up"

    def note(message):
        with state.lock:
            state.progress = message

    try:
        top, all_scored = run_scan(config, progress_cb=note)

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
            state.progress = ""


def start_background_worker(state, config):
    """
    Launch the repeating refresh loop on its own thread so the web
    server stays responsive while prices are being fetched.
    """
    minutes = config["schedule"]["refresh_minutes"]

    # Apply the IPv4 restriction BEFORE the worker thread exists. Doing it
    # later, in the web app setup, left a window where the first scan could
    # start its lookup on IPv6 and hang. See net.py.
    if config["data_source"].get("force_ipv4", True):
        from src import net
        net.force_ipv4()

    def loop():
        # Scan immediately so the page is not empty on first load.
        refresh(state, config)

        while True:
            time.sleep(minutes * 60)

            if market_hours.is_market_open(config):
                refresh(state, config)
            else:
                print(f"  [{datetime.now():%H:%M:%S}] Market closed - skipping")

    thread = threading.Thread(target=loop, daemon=True, name="scan-loop")
    thread.start()
    state.worker_pid = os.getpid()
    return thread


# ----------------------------------------------------------------------
#  Making sure the scan runs in the process that serves the page
# ----------------------------------------------------------------------
#
# Some hosts load the app once, start it, and then copy the whole process
# to handle web requests. A copy gets the scan's status frozen at the
# moment it was made, but not the scan itself - threads do not survive
# the copy. The page then shows "Scanning" for ever, because nothing in
# that copy will ever update it.
#
# ensure_worker() runs on every page request. If the scan belongs to a
# different process, it starts a fresh one here.

_start_lock = threading.Lock()


def _reset_after_copy():
    """Locks copied mid-use stay locked for ever, so make new ones."""
    global _start_lock
    _start_lock = threading.Lock()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_after_copy)


def ensure_worker(state, config):
    if state.worker_pid == os.getpid():
        return                               # already running here

    with _start_lock:
        if state.worker_pid == os.getpid():
            return

        print(f"  Scan belongs to process {state.worker_pid}, page served "
              f"by {os.getpid()} - starting a scan here", flush=True)

        # Everything copied from the other process is stale. Start clean,
        # including a fresh lock in case the copy caught it mid-use.
        state.lock = threading.Lock()
        state.is_refreshing = False
        state.progress = ""
        state.scan_started = None
        state.last_error = None

        start_background_worker(state, config)
