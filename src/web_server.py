"""
web_server.py
-------------
Serves the screener as a web page you can open on your computer or
your phone.

Two routes:
  /          the page you look at
  /api/data  the same numbers as JSON, if you ever want them elsewhere
"""

import os
import socket

from flask import Flask, render_template, jsonify

from src import sparkline, market_hours

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"
)


def local_ip():
    """
    Best guess at this machine's address on your home network, so we can
    print the URL to type into your phone.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))          # no data is sent, just routing
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _decorate(rows, config):
    """Attach a sparkline SVG to each row before display."""
    days = config.get("web", {}).get("sparkline_days", 30)
    out = []
    for r in rows:
        r = dict(r)
        r["sparkline"] = sparkline.make(r.get("history", []), days=days)
        out.append(r)
    return out


def create_app(state, config):
    app = Flask(__name__, template_folder=TEMPLATE_DIR)

    @app.route("/")
    def index():
        snap = state.snapshot()
        return render_template(
            "index.html",
            rows=_decorate(snap["rows"], config),
            scanned=snap["scanned"],
            last_updated=snap["last_updated"],
            last_error=snap["last_error"],
            is_refreshing=snap["is_refreshing"],
            market_status=market_hours.status_text(config),
            config=config,
            mode=config["scoring"].get("mode", "dip").upper(),
            threshold=config["scoring"]["buy_threshold"],
            lookback=config["indicators"].get("lookback_days", 3),
            refresh_minutes=config["schedule"]["refresh_minutes"],
            # A free host shuts the app down when nobody is looking, so the
            # first page view after a gap arrives before the scan finishes.
            # Reload quickly until data appears, then settle down.
            page_refresh=15 if snap["last_updated"] is None else 60,
        )

    @app.route("/healthz")
    def healthz():
        """Lets the host confirm the app started, without running a scan."""
        return {"ok": True}

    @app.route("/api/data")
    def api_data():
        snap = state.snapshot()
        rows = []
        for r in snap["rows"]:
            r = {k: v for k, v in r.items() if k != "history"}
            rows.append(r)
        return jsonify({
            "rows": rows,
            "scanned": snap["scanned"],
            "last_updated": snap["last_updated"].isoformat()
                            if snap["last_updated"] else None,
            "error": snap["last_error"],
        })

    return app
