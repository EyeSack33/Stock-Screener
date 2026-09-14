"""
refresh_sp500.py
----------------
Updates data/sp500.csv with the current S&P 500 members.

    python refresh_sp500.py

Companies join and leave the index a handful of times a year, so running
this every month or two is plenty. If it fails, the old list keeps
working - nothing breaks.
"""

import os
import shutil
import sys
import urllib.request

from src.universe import SP500_URL

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(ROOT, "data", "sp500.csv")


def main():
    print(f"Downloading the current S&P 500 list...")

    try:
        with urllib.request.urlopen(SP500_URL, timeout=30) as response:
            body = response.read().decode("utf-8")
    except Exception as e:
        print(f"\nDownload failed: {e}")
        print("Your existing list is untouched, so the screener still works.\n")
        return 1

    lines = [ln for ln in body.splitlines() if ln.strip()]
    if len(lines) < 400 or not lines[0].lower().startswith("symbol"):
        print("\nThat did not look like the expected list. Nothing was changed.\n")
        return 1

    # Keep a backup so a bad download is easy to undo
    if os.path.exists(TARGET):
        shutil.copy(TARGET, TARGET + ".backup")

    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(body)

    print(f"Saved {len(lines) - 1} companies to data/sp500.csv")
    print("The previous version is at data/sp500.csv.backup\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
