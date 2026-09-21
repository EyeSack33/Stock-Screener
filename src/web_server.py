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

from src import sparkline, market_hours, net

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


def _source_label(config):
    """Plain-English description of where the prices are coming from."""
    ds = config["data_source"]
    provider = ds.get("provider", "").lower()
    if provider == "alpaca":
        if ds.get("feed", "iex").lower() == "sip":
            return "Prices from Alpaca, all exchanges combined."
        return "Prices from Alpaca's IEX feed."
    if provider == "yfinance":
        return "Prices from Yahoo, delayed roughly 15 minutes."
    if provider == "mock":
        return "SAMPLE DATA - these are not real prices."
    return f"Prices from {provider}."


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
    # Must run before any outbound request. See net.py for why.
    if config["data_source"].get("force_ipv4", True):
        net.force_ipv4()

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
            source_label=_source_label(config),
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

        # ---- Which code is actually running? --------------------------
        # GitHub's web upload can drop a file at the top level instead of
        # inside src/. The build still succeeds, but the app keeps loading
        # the old copy. These checks look at what is really loaded.
        import hashlib, inspect, glob as _glob
        lines.append("CODE ON THIS SERVER")
        lines.append("-" * 54)
        lines.append(f"  Build: {net.BUILD}")

        def check(label, test):
            try:
                ok = bool(test())
            except Exception:
                ok = False
            lines.append(f"  {'OK ' if ok else 'OLD'}  {label}")
            return ok

        from src import data_feed as _df
        all_current = all([
            check("data_feed.py has the 90s hard deadline",
                  lambda: "run_with_deadline" in vars(_df)),
            check("net.py is present",
                  lambda: __import__("src.net")),
            check("scheduler.py forces IPv4 before scanning",
                  lambda: "force_ipv4" in inspect.getsource(
                      __import__("src.scheduler", fromlist=["x"]).start_background_worker)),
            check("alpaca_check.py uses short timeouts",
                  lambda: __import__("src.alpaca_check", fromlist=["x"]).TIMEOUT_SECONDS <= 10),
        ])
        if not all_current:
            lines.append("")
            lines.append("  >> A file marked OLD did not reach src/ on GitHub.")
            lines.append("     Look at the top level of your repository: if")
            lines.append("     that file is sitting there, it went to the wrong")
            lines.append("     place. Delete it there and upload it into src/.")

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        top_level_scripts = {"main.py", "serve.py", "wsgi.py", "refresh_sp500.py",
                             "check_data.py", "check_alpaca.py"}
        at_top = {os.path.basename(f) for f in _glob.glob(os.path.join(root, "*.py"))}
        in_src = {os.path.basename(f) for f in _glob.glob(os.path.join(root, "src", "*.py"))}
        extra_top = sorted(at_top - top_level_scripts)
        extra_src = sorted(in_src & top_level_scripts)
        if extra_top or extra_src:
            lines.append("")
            lines.append("  Spare copies (harmless - the app ignores them,")
            lines.append("  tidy up whenever convenient):")
            if extra_top:
                lines.append(f"    at the top level, delete: {', '.join(extra_top)}")
            if extra_src:
                lines.append(f"    inside src/, delete:      {', '.join(extra_src)}")
        lines.append("")
        lines.append("  File fingerprints:")
        for f in sorted(_glob.glob(os.path.join(root, "src", "*.py"))):
            digest = hashlib.sha1(open(f, "rb").read()).hexdigest()[:8]
            lines.append(f"    {os.path.basename(f):<20} {digest}")
        lines.append("")

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

        if config["data_source"]["provider"] == "alpaca":
            from src import alpaca_check
            lines.append("=" * 54)
            lines.append("ALPACA KEY DIAGNOSTIC")
            lines.append("=" * 54)
            try:
                lines.extend(alpaca_check.run(
                    config["data_source"].get("api_key", ""),
                    config["data_source"].get("api_secret", ""),
                ))
            except Exception as e:
                lines.append(f"Diagnostic itself failed: {e}")
            lines.append("")

        if config["data_source"]["provider"] == "alpaca":
            # Run the exact request the background scan makes, but from
            # this page. If it works here while the scan hangs, the fault
            # is the background scan itself, not the key or the network.
            lines.append("=" * 54)
            lines.append("THE SCAN'S OWN REQUEST, RUN FROM THIS PAGE")
            lines.append("=" * 54)
            try:
                from src.data_feed import get_provider
                started = time.time()
                got = net.run_with_deadline(
                    40, lambda: get_provider(config).fetch(["AAPL"], 60))
                took = time.time() - started
                if got:
                    lines.append(f"  OK in {took:.1f}s - AAPL {got[0]['price']:.2f}, "
                                 f"{len(got[0]['history'])} days of history")
                    lines.append("")
                    if snap["is_refreshing"] and not snap["last_updated"]:
                        lines.append("  This request works, yet the background scan")
                        lines.append("  is stuck. The fault is the background scan,")
                        lines.append("  not your key or the network. See /threads.")
                else:
                    lines.append(f"  Returned nothing after {took:.1f}s")
            except net.DeadlineExceeded:
                lines.append("  HUNG - no result in 40s, same as the scan.")
                lines.append("  So the request itself hangs, wherever it runs.")
            except Exception as e:
                lines.append(f"  FAILED - {e}")
            return Response("\n".join(lines), mimetype="text/plain")

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

    @app.route("/net")
    def network_check():
        """Tests the connection to Alpaca one layer at a time."""
        from flask import Response
        return Response("\n".join(net.probe()), mimetype="text/plain")

    @app.route("/threads")
    def threads():
        """
        Shows the exact line of code every part of the app is on right now.
        Used to find where a stuck scan is stuck, instead of guessing.
        Shows file names and line numbers only - never variable values, so
        no keys or secrets can appear here.
        """
        import sys as _sys, threading as _th, traceback as _tb
        from flask import Response
        names = {t.ident: t.name for t in _th.enumerate()}
        out = [f"Build {net.BUILD}   threads: {len(names)}", ""]
        for ident, frame in _sys._current_frames().items():
            stack = _tb.extract_stack(frame)
            ours = [f for f in stack if "/src/" in f.filename
                    or f.filename.endswith("wsgi.py")]
            here = stack[-1]
            out.append("=" * 60)
            out.append(f"{names.get(ident, 'unknown')}")
            out.append(f"  now in: {here.name}()  "
                       f"{here.filename.split('/')[-1]}:{here.lineno}")
            for f in ours[-6:]:
                out.append(f"    {f.filename.split('/')[-1]}:{f.lineno}  "
                           f"{f.name}()  {(f.line or '').strip()[:60]}")
            out.append("")
        return Response("\n".join(out), mimetype="text/plain")

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
            "build": net.BUILD,
            "provider": config["data_source"]["provider"],
            "feed": config["data_source"].get("feed"),
            "limit": config["universe"].get("limit"),
        })

    return app
