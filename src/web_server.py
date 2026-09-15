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
import time
from datetime import datetime

# When this process started. If this keeps resetting to a few seconds,
# the app is being restarted rather than running continuously.
PROCESS_STARTED = time.time()

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
            page_refresh=10 if snap["last_updated"] is None else 60,
            progress=snap["progress"],
            elapsed=(int((datetime.now() - snap["scan_started"]).total_seconds())
                     if snap["scan_started"] and not snap["last_updated"] else None),
        )

    @app.route("/debug")
    def debug():
        """
        A plain-text health report you can open in a browser.
        Built for hosts like Render's free plan, which give you no
        terminal to run check_data.py in.
        """
        from flask import Response

        snap = state.snapshot()
        lines = []

        def say(label, value):
            lines.append(f"{label:<24} {value}")

        uptime = int(time.time() - PROCESS_STARTED)
        say("App running for", f"{uptime} seconds")
        if uptime < 90:
            lines.append("  >> If this stays low on every reload, the app is")
            lines.append("     restarting and no scan can ever finish.")
        lines.append("")

        say("Scan ever completed", "yes" if snap["last_updated"] else "NO")
        say("Last updated", snap["last_updated"] or "never")
        say("Currently scanning", "yes" if snap["is_refreshing"] else "no")
        say("Progress", snap["progress"] or "-")
        if snap["scan_started"]:
            running = int((datetime.now() - snap["scan_started"]).total_seconds())
            say("Current scan age", f"{running} seconds")
        say("Stocks passing", snap["scanned"])
        say("Last error", snap["last_error"] or "none")
        lines.append("")

        say("Provider", config["data_source"]["provider"])
        say("Scan limit", config["universe"].get("limit", 0) or "all")
        say("Batch size", config["data_source"].get("batch_size", 100))
        lines.append("")

        lines.append("-" * 52)
        lines.append("Live test: asking the provider for one stock")
        lines.append("-" * 52)
        try:
            from src.data_feed import get_provider
            provider = get_provider(config)
            started = time.time()
            got = provider.fetch(["AAPL"], 60)
            took = time.time() - started

            if not got:
                say("Result", f"EMPTY after {took:.1f}s")
            else:
                row = got[0]
                say("Result", f"OK in {took:.1f}s")
                say("AAPL price", f"{row['price']:.2f}")
                say("Days of history", len(row["history"]))
                lines.append("")
                lines.append("The data source works from here. If the page is")
                lines.append("still stuck, the app is restarting mid-scan.")
        except Exception as e:
            say("Result", f"FAILED - {type(e).__name__}")
            lines.append("")
            lines.append(str(e)[:500])
            lines.append("")
            if config["data_source"]["provider"] == "yfinance":
                lines.append("Yahoo blocks hosted servers. Switch to the")
                lines.append("alpaca provider - see DEPLOY.md.")

        return Response("\n".join(lines), mimetype="text/plain")

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
            # These three answer "is it working or is it stuck?"
            "is_refreshing": snap["is_refreshing"],
            "progress": snap["progress"],
            "scan_age_seconds": (
                int((datetime.now() - snap["scan_started"]).total_seconds())
                if snap["scan_started"] else None),
            "app_uptime_seconds": int(time.time() - PROCESS_STARTED),
        })

    return app
