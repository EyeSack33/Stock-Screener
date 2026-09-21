"""
market_hours.py
---------------
Answers one question: is the US stock market open right now?

Used so the screener does not hammer Yahoo overnight and on weekends
when nothing is changing. Turn it off with market_hours_only: false
in config.yaml.

Note: this checks weekday and clock time only. It does not know about
holidays like Thanksgiving, so on those days it will refresh against
a market that is closed. Harmless, just slightly wasteful.
"""

from datetime import datetime, time

try:
    from zoneinfo import ZoneInfo          # Python 3.9+
except ImportError:                         # pragma: no cover
    ZoneInfo = None

OPEN_TIME = time(9, 30)
CLOSE_TIME = time(16, 0)


def now_in_market_tz(config):
    """Current time in the timezone set in config.yaml."""
    tz_name = config["schedule"].get("timezone", "America/New_York")
    if ZoneInfo is None:
        return datetime.now()
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        # Unknown timezone name - fall back rather than crash
        return datetime.now(ZoneInfo("America/New_York"))


def is_market_open(config):
    """True if it is a weekday between 9:30am and 4:00pm market time."""
    if not config["schedule"].get("market_hours_only", True):
        return True                         # user asked us to ignore hours

    now = now_in_market_tz(config)

    if now.weekday() >= 5:                  # 5 = Saturday, 6 = Sunday
        return False

    return OPEN_TIME <= now.time() <= CLOSE_TIME


def status_text(config):
    """A short human-readable status for the web page."""
    now = now_in_market_tz(config)
    stamp = now.strftime("%a %H:%M %Z")
    if not config["schedule"].get("market_hours_only", True):
        return f"Always-on mode - {stamp}"
    return ("Market open - " if is_market_open(config) else "Market closed - ") + stamp
