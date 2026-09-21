"""
ratings.py
----------
Wall Street analyst ratings, from Finnhub's free recommendation endpoint.

For each stock, Finnhub reports how many analysts currently rate it
Strong Buy, Buy, Hold, Sell or Strong Sell. We turn those counts into a
consensus: a number from 1 (everyone says Strong Sell) to 5 (everyone
says Strong Buy), and a plain label.

Two things worth knowing about this data:
  * It is a monthly snapshot. It will not react to a drop that happened
    today, so a stock that fell on bad news this morning may still show
    last month's rating.
  * Consensus ratings lean positive. Most large companies are rated Buy,
    so a Buy on its own says less than it sounds like it does.

Ratings change slowly, so each one is kept in memory for `cache_hours`
and only looked up again after that.
"""

import json
import time
import urllib.parse

from src.data_feed import DataFeedError
from src.net import http_get_isolated

URL = "https://finnhub.io/api/v1/stock/recommendation"

# Consensus cut-offs, highest first
LABELS = [(4.5, "Strong Buy"), (3.5, "Buy"), (2.5, "Hold"),
          (1.5, "Sell"), (0.0, "Strong Sell")]

_cache = {}          # symbol -> (time fetched, rating dict or None)


class RatingsError(DataFeedError):
    """A ratings problem serious enough to report on the page."""


def to_finnhub(symbol):
    """Finnhub writes share classes with a dot: BRK-B becomes BRK.B."""
    return symbol.replace("-", ".")


def summarise(entry):
    """Turn one month of analyst counts into a consensus."""
    counts = [int(entry.get(k) or 0)
              for k in ("strongBuy", "buy", "hold", "sell", "strongSell")]
    strong_buy, buy, hold, sell, strong_sell = counts
    total = sum(counts)
    if total == 0:
        return None

    consensus = (5 * strong_buy + 4 * buy + 3 * hold
                 + 2 * sell + 1 * strong_sell) / total
    label = next(name for cutoff, name in LABELS if consensus >= cutoff)

    return {
        "strong_buy": strong_buy, "buy": buy, "hold": hold,
        "sell": sell, "strong_sell": strong_sell,
        "analysts": total,
        "consensus": round(consensus, 2),
        "label": label,
        "buy_pct": round((strong_buy + buy) / total * 100),
        "period": entry.get("period"),
    }


def fetch_one(symbol, key, timeout=15):
    """
    Look up one stock. Returns a rating, None if no analysts cover it,
    or the string "RATE_LIMITED" if Finnhub asked us to slow down.
    """
    query = urllib.parse.urlencode({"symbol": to_finnhub(symbol)})
    # The key goes in a header rather than the address, so it never ends
    # up in any log that records web addresses.
    status, body = http_get_isolated(f"{URL}?{query}", headers={
        "X-Finnhub-Token": key,
        "accept": "application/json",
    }, timeout=timeout)

    if status == 200:
        try:
            months = json.loads(body)
        except ValueError:
            raise RatingsError("Finnhub sent data that could not be read.")
        if not months:
            return None
        latest = max(months, key=lambda m: m.get("period") or "")
        return summarise(latest)

    if status == 401:
        raise RatingsError(
            "Finnhub rejected your key (401). Check FINNHUB_API_KEY in "
            "Render's Environment tab."
        )
    if status == 403:
        raise RatingsError(
            "Finnhub refused the ratings request (403). The recommendation "
            "endpoint may have moved to a paid plan."
        )
    if status == 429:
        return "RATE_LIMITED"
    if status is None:
        raise RatingsError(f"No answer from Finnhub: {body}")
    raise RatingsError(f"Finnhub error {status}: {' '.join(body.split())[:120]}")


def attach(rows, config, progress_cb=None):
    """
    Add a "rating" to each row. Rows should arrive biggest drop first, so
    that if the lookup cap is reached, it is the smallest drops that miss
    out. Returns the number of fresh lookups made.
    """
    cfg = config.get("ratings", {})
    key = cfg.get("api_key", "")
    ttl = cfg.get("cache_hours", 24) * 3600
    pause = cfg.get("pause_seconds", 1.1)      # free plan: 60 a minute
    cap = cfg.get("max_lookups", 40)

    looked_up = 0
    rate_limited = False

    for n, row in enumerate(rows, start=1):
        symbol = row["ticker"]
        cached = _cache.get(symbol)

        if cached and time.time() - cached[0] < ttl:
            row["rating"] = cached[1]
            continue

        if looked_up >= cap or rate_limited:
            row["rating"] = None
            row["rating_pending"] = True       # will be looked up next scan
            continue

        if progress_cb:
            progress_cb(f"Fetching analyst ratings, {n} of {len(rows)}")

        if looked_up:
            time.sleep(pause)

        result = fetch_one(symbol, key)
        if result == "RATE_LIMITED":
            print("  Finnhub rate limit - waiting 15s and trying once more",
                  flush=True)
            time.sleep(15)
            result = fetch_one(symbol, key)
            if result == "RATE_LIMITED":
                rate_limited = True
                row["rating"] = None
                row["rating_pending"] = True
                continue

        looked_up += 1
        _cache[symbol] = (time.time(), result)
        row["rating"] = result

    print(f"  Ratings: {looked_up} looked up, "
          f"{len(rows) - looked_up} from memory or deferred", flush=True)
    return looked_up
