"""
indicators.py
-------------
Turns raw prices into the numbers we score on:

  1. daily_change_pct   - today's move, in percent
  2. recent_change_pct  - the move over the last few days (lookback_days)
  3. short_ma / long_ma - moving averages set in config.yaml
  4. ma_distance_pct    - how far price sits above/below the short MA

A moving average is just "the average closing price over the last N days".
Today's still-moving bar is included by default, so the averages react to
what is happening right now. Set include_today_in_ma: false in config.yaml
if you would rather use only completed trading days.
"""


def percent_change(new, old):
    """Percent difference between two prices. Returns 0 if old is 0."""
    if not old:
        return 0.0
    return ((new - old) / old) * 100


def moving_average(closes, days):
    """Average of the last `days` closing prices."""
    if len(closes) < days:
        return None          # not enough history yet
    window = closes[-days:]
    return sum(window) / len(window)


def compute(quote, config):
    """Take one quote from data_feed and add the indicator values to it."""
    ind = config["indicators"]
    short_days = ind["short_ma_days"]
    long_days = ind["long_ma_days"]
    lookback = ind.get("lookback_days", 3)
    include_today = ind.get("include_today_in_ma", True)

    price = quote["price"]
    full_history = quote["history"]          # last item is today

    # Which closes feed the moving averages
    closes = full_history if include_today else full_history[:-1]

    short_ma = moving_average(closes, short_days)
    long_ma = moving_average(closes, long_days)

    # Price `lookback` trading days ago. history[-1] is today, so 3 days
    # back is history[-4].
    recent_change = None
    if len(full_history) > lookback:
        recent_change = percent_change(price, full_history[-(lookback + 1)])

    return {
        "ticker": quote["ticker"],
        "price": price,
        "history": full_history,          # kept for the web page's mini chart
        "prev_close": quote["prev_close"],
        "daily_change_pct": percent_change(price, quote["prev_close"]),
        "recent_change_pct": recent_change,
        "lookback_days": lookback,
        "short_ma": short_ma,
        "long_ma": long_ma,
        # Negative = price has dropped below its short-term average
        "ma_distance_pct": percent_change(price, short_ma) if short_ma else None,
        # Positive = short-term trend sits above long-term trend
        "ma_spread_pct": percent_change(short_ma, long_ma) if short_ma and long_ma else None,
    }


def compute_all(quotes, config):
    """Run compute() over every quote, skipping any with missing data."""
    results = []
    for q in quotes:
        row = compute(q, config)
        if row["short_ma"] is None or row["long_ma"] is None:
            continue         # not enough price history for this ticker
        if row["recent_change_pct"] is None:
            continue
        results.append(row)
    return results
