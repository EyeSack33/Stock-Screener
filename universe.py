"""
universe.py
-----------
Decides WHICH stocks to scan. Three options, set by `source` in the
`universe` section of config.yaml:

  list    - the tickers you type into config.yaml
  sp500   - all ~500 companies in the S&P 500
  file    - one ticker per line in a text file you maintain

The S&P 500 list ships with the project in data/sp500.csv so it works
offline. Run `python refresh_sp500.py` occasionally to update it, since
companies join and leave the index a few times a year.
"""

import csv
import os

SP500_URL = ("https://raw.githubusercontent.com/datasets/"
             "s-and-p-500-companies/master/data/constituents.csv")


class UniverseError(Exception):
    pass


def to_yahoo(symbol):
    """
    Yahoo writes share classes with a dash, not a dot.
    BRK.B becomes BRK-B, BF.B becomes BF-B.
    """
    return symbol.strip().upper().replace(".", "-")


def load_sp500(project_root):
    """Read the bundled S&P 500 list."""
    path = os.path.join(project_root, "data", "sp500.csv")
    if not os.path.exists(path):
        raise UniverseError(
            f"Missing {path}\nRun: python refresh_sp500.py"
        )

    tickers = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            symbol = row.get("Symbol", "").strip()
            if symbol:
                tickers.append(to_yahoo(symbol))
    return tickers


def load_file(project_root, file_path):
    """Read a plain text file, one ticker per line. # starts a comment."""
    if not os.path.isabs(file_path):
        file_path = os.path.join(project_root, file_path)

    if not os.path.exists(file_path):
        raise UniverseError(f"Ticker file not found: {file_path}")

    tickers = []
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line:
                tickers.append(to_yahoo(line))
    return tickers


def resolve(config):
    """Return the final, de-duplicated list of tickers to scan."""
    uni = config["universe"]
    source = uni.get("source", "list").lower()
    root = config["_project_root"]

    if source == "list":
        tickers = [to_yahoo(t) for t in uni.get("tickers", [])]
    elif source == "sp500":
        tickers = load_sp500(root)
    elif source == "file":
        tickers = load_file(root, uni.get("file_path", "watchlist.txt"))
    else:
        raise UniverseError(
            f"Unknown universe source '{source}'. Use list, sp500, or file."
        )

    # Drop anything on the exclude list
    excluded = {to_yahoo(t) for t in uni.get("exclude", []) or []}
    tickers = [t for t in tickers if t not in excluded]

    # De-duplicate while keeping the original order
    seen = set()
    unique = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    # `limit` is handy for testing against a big universe without waiting
    limit = uni.get("limit", 0) or 0
    if limit > 0:
        unique = unique[:limit]

    if not unique:
        raise UniverseError(
            "No tickers to scan. Check the `universe` section of config.yaml."
        )

    return unique
