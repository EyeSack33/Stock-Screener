"""
scoring.py
----------
Combines the indicators into a single "buy strength" score from 0 to 100.

Two modes, set by `mode` in config.yaml:

  dip       - a falling price scores HIGHER (buying weakness)
  momentum  - a rising price scores HIGHER (following strength)

How it works:
  - Each indicator becomes its own 0-100 sub-score.
  - Those sub-scores are blended using the weights in config.yaml.
  - 50 is neutral. Above 50 is a stronger match for your rules.

IMPORTANT: this is a screening tool, not investment advice. A high score
only means the stock matched the rules you set.
"""


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def _scale(value, full_scale_pct):
    """
    Convert a percentage into a 0-100 score centred on 50.

        0%             -> 50 (neutral)
        +full_scale    -> 100
        -full_scale    -> 0
    """
    if not full_scale_pct:
        return 50.0
    return _clamp(50 + (value / full_scale_pct) * 50)


def _directional(value, full_scale_pct, mode):
    """
    In dip mode we flip the sign, so a -5% move becomes a top score
    instead of a bottom one.
    """
    if mode == "dip":
        value = -value
    return _scale(value, full_scale_pct)


def score_row(row, config):
    """Score one stock. Returns a copy of the row with score fields added."""
    cfg = config["scoring"]
    mode = cfg.get("mode", "dip").lower()
    weights = cfg["weights"]
    dip_scale = cfg.get("dip_full_scale_pct", 5.0)
    ma_scale = cfg.get("ma_distance_full_scale_pct", 5.0)
    trend_scale = cfg.get("ma_trend_full_scale_pct", 5.0)

    # 1. Today's move. In dip mode, -5% scores 100.
    s_today = _directional(row["daily_change_pct"], dip_scale, mode)

    # 2. The move over the last few days (lookback_days in config).
    s_recent = _directional(row["recent_change_pct"], dip_scale, mode)

    # 3. Distance from the short moving average. In dip mode, trading
    #    below the average scores higher (potentially oversold).
    s_distance = _directional(row["ma_distance_pct"], ma_scale, mode)

    # 4. Long-term trend health. NOT flipped - an uptrend is good in
    #    either mode. Default weight is 0, so it is off unless you
    #    raise ma_trend in config.yaml.
    s_trend = _scale(row["ma_spread_pct"], trend_scale)

    total = (
        s_today * weights.get("dip_today", 0.0)
        + s_recent * weights.get("dip_recent", 0.0)
        + s_distance * weights.get("ma_distance", 0.0)
        + s_trend * weights.get("ma_trend", 0.0)
    )

    row = dict(row)
    row["score_today"] = round(s_today, 1)
    row["score_recent"] = round(s_recent, 1)
    row["score_ma_distance"] = round(s_distance, 1)
    row["score_ma_trend"] = round(s_trend, 1)
    row["buy_score"] = round(total, 1)
    row["signal"] = _label(total, config)
    return row


def _label(score, config):
    threshold = config["scoring"]["buy_threshold"]
    if score >= threshold + 15:
        return "STRONG BUY"
    if score >= threshold:
        return "BUY"
    if score >= 40:
        return "HOLD"
    return "AVOID"


def rank(rows, config):
    """Score every stock, filter by the threshold, sort best first."""
    scored = [score_row(r, config) for r in rows]
    threshold = config["scoring"]["buy_threshold"]
    max_results = config["scoring"]["max_results"]

    passing = [r for r in scored if r["buy_score"] >= threshold]
    passing.sort(key=lambda r: r["buy_score"], reverse=True)
    return passing[:max_results], scored
