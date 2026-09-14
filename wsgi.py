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

from src.config_loader import load_config
from src.scheduler import ScreenerState, start_background_worker
from src.web_server import create_app

config = load_config()
state = ScreenerState()
start_background_worker(state, config)

app = create_app(state, config)
