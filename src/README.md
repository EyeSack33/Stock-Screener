# Dip Screener

Scans the S&P 500 and ranks the stocks that have fallen, using today's
move, a 3-day move, and how far the price sits below its 20-day average.

## Two ways to run this

**Online (recommended)** - free hosting on Render gives you a web
address that works from any device, anywhere. No terminal needed.
See DEPLOY.md.

**On your own computer** - faster, but only reachable while your
computer is running. Double-click START-MAC.command or
START-WINDOWS.bat, or follow the manual steps below.

## Manual setup

    pip install -r requirements.txt

## Run it

    python serve.py        # web page, refreshes every 15 minutes
    python main.py --once  # one-off text table in your terminal

`serve.py` prints two addresses. Use the `localhost` one on your
computer, and the other on your phone while it is on the same Wi-Fi.

To reach it from anywhere, see DEPLOY.md.

## Settings

Everything lives in `config.yaml`. The most useful knobs:

| Setting | What it does |
|---|---|
| `universe.source` | `sp500`, `list`, or `file` |
| `universe.limit` | Cap the scan size. 0 means everything. |
| `refresh_minutes` | How often to re-check (default 15) |
| `lookback_days` | Your short-term window (default 3) |
| `dip_full_scale_pct` | The drop size that earns a perfect score (default 5%) |
| `weights` | How much each factor counts. Must total 1.0 |
| `buy_threshold` | Minimum score to appear in the list |
| `mode` | `dip` rewards falling prices, `momentum` rewards rising ones |

Run `python refresh_sp500.py` every month or two to update the company
list, since the index changes a few times a year.

## Where things live

| File | What it does |
|---|---|
| `config.yaml` | All settings. The only file you edit. |
| `serve.py` | Starts the web page. |
| `main.py` | Terminal version. |
| `wsgi.py` | Entry point used by Render. |
| `src/config_loader.py` | Reads and checks config.yaml. |
| `src/universe.py` | Decides which stocks to scan. |
| `src/data_feed.py` | Gets prices from Yahoo. |
| `src/indicators.py` | Daily change, 3-day change, moving averages. |
| `src/scoring.py` | Turns indicators into a 0-100 score. |
| `src/scheduler.py` | Background refresh loop. |
| `src/market_hours.py` | Knows when the market is open. |
| `src/sparkline.py` | Draws the mini price charts. |
| `src/web_server.py` | The web routes. |
| `src/output.py` | Terminal table and CSV. |
| `templates/index.html` | The page layout. |

## Notes

Nothing is saved between runs — each scan replaces the last. Yahoo prices
are delayed by roughly 15 minutes. The market-hours check knows about
weekends but not holidays.

This is a screening tool, not investment advice.
