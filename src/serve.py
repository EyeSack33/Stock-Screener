"""
serve.py
--------
Starts the screener as a web page.

    python serve.py

Then open the address it prints. The same address works from your phone
as long as the phone is on the same Wi-Fi network.

For the plain text version in your terminal instead, use:

    python main.py --once
"""

import sys

from src.config_loader import load_config, ConfigError
from src.scheduler import ScreenerState, start_background_worker
from src.web_server import create_app, local_ip


def main():
    try:
        config = load_config()
    except ConfigError as e:
        print(f"\nConfiguration problem:\n  {e}\n")
        return 1

    web = config.get("web", {})
    host = web.get("host", "0.0.0.0")
    port = web.get("port", 8000)

    state = ScreenerState()

    print("\nStock screener starting.")
    print(f"  On this computer:  http://localhost:{port}")
    if host == "0.0.0.0":
        print(f"  On your phone:     http://{local_ip()}:{port}")
        print("  (phone must be on the same Wi-Fi)")
    print(f"\n  Refreshing every {config['schedule']['refresh_minutes']} minutes.")
    print("  Press Ctrl+C to stop.\n")

    start_background_worker(state, config)

    app = create_app(state, config)
    try:
        # debug=False matters here: debug mode would restart the app and
        # run the background worker twice.
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\nStopped.\n")
    except OSError as e:
        print(f"\nCould not start the server on port {port}: {e}")
        print("Another program may be using it. Change `port` in config.yaml.\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
