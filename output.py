"""
output.py
---------
Displays the results. Keeping this separate means we can later send the
same list to a web page, an email, or a spreadsheet without touching the
scoring logic.
"""

import csv
import os
from datetime import datetime

COLUMNS = ["ticker", "price", "daily_change_pct", "recent_change_pct",
           "short_ma", "ma_distance_pct", "buy_score", "signal"]

HEADERS = {
    "ticker": "Ticker",
    "price": "Price",
    "daily_change_pct": "Day %",
    "recent_change_pct": "3-Day %",
    "short_ma": "Short MA",
    "ma_distance_pct": "vs MA %",
    "buy_score": "Score",
    "signal": "Signal",
}


def _fmt(key, value):
    if value is None:
        return "-"
    if key in ("price", "short_ma", "long_ma"):
        return f"{value:,.2f}"
    if key in ("daily_change_pct", "recent_change_pct", "ma_distance_pct"):
        return f"{value:+.2f}%"
    if key == "buy_score":
        return f"{value:.1f}"
    return str(value)


def to_console(rows, config, scanned_count):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    provider = config["data_source"]["provider"]

    print()
    print("=" * 74)
    mode = config["scoring"].get("mode", "dip").upper()
    print(f"  BUY CANDIDATES   {stamp}   ({mode} mode, source: {provider})")
    print("=" * 74)

    if not rows:
        print(f"\n  No stocks scored above {config['scoring']['buy_threshold']}"
              f" out of {scanned_count} scanned.\n")
        print("=" * 74)
        return

    # Rename the 3-day column to match whatever lookback_days is set to
    lookback = config["indicators"].get("lookback_days", 3)
    headers = dict(HEADERS)
    headers["recent_change_pct"] = f"{lookback}-Day %"

    widths = {c: max(len(headers[c]), 9) for c in COLUMNS}
    header = "  ".join(headers[c].ljust(widths[c]) for c in COLUMNS)
    print(header)
    print("-" * len(header))

    for r in rows:
        print("  ".join(_fmt(c, r.get(c)).ljust(widths[c]) for c in COLUMNS))

    print("-" * len(header))
    print(f"  {len(rows)} of {scanned_count} stocks passed the filter.")
    print("  Screening output only. Not investment advice.")
    print("=" * 74)


def to_csv(rows, config):
    path = config["output"]["csv_path"]
    if not os.path.isabs(path):
        path = os.path.join(config["_project_root"], path)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    stamp = datetime.now().isoformat(timespec="seconds")
    new_file = not os.path.exists(path)

    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["timestamp"] + COLUMNS)
        for r in rows:
            writer.writerow([stamp] + [r.get(c) for c in COLUMNS])

    print(f"  Saved {len(rows)} rows to {path}")


def render(rows, config, scanned_count):
    mode = config["output"]["mode"].lower()
    to_console(rows, config, scanned_count)
    if mode == "csv":
        to_csv(rows, config)
