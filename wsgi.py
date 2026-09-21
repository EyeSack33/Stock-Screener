"""
wsgi.py
-------
The entry point used by a hosting service such as Render.

Locally you run `python serve.py`. On a host, a program called gunicorn
imports `app` from this file instead. The difference matters because
gunicorn handles the web serving itself, so we only start the background
price refresher here.

IMPORTANT: run gunicorn with a single worker. Each worker would start its
own refresh loop, meaning several copies fetching prices and writing
duplicate history.
"""

import sys

# Render reads our log output from a pipe, and Python buffers writes to
# pipes. Without this, nothing appears in the Logs tab until the buffer
# fills, which can be never.
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except AttributeError:
    pass

from src.config_loader import load_config
from src.scheduler import ScreenerState
from src.web_server import create_app

config = load_config()
state = ScreenerState()

print("=" * 52, flush=True)
print("Dip screener starting up", flush=True)
print(f"  provider : {config['data_source']['provider']}", flush=True)
print(f"  limit    : {config['universe'].get('limit', 0) or 'all'}", flush=True)
print("=" * 52, flush=True)

# The scan is NOT started here. Some hosts load this file once and then
# copy the process to serve pages; a scan started here would run in the
# original, invisible to the page, and waste API calls. Instead the first
# page request starts it, in the process that will actually use it
# (see scheduler.ensure_worker). Render's health check makes that first
# request within seconds of startup.

app = create_app(state, config)
