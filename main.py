"""
main.py
-------
The entry point. Run it with:

    python main.py            # loop forever, refreshing on a timer
    python main.py --once     # run one scan and exit (good for testing)

All settings come from config.yaml. There are no API keys or tickers in
this file on purpose.
"""

import sys
import time
from datetime import datetime

from src.config_loader import load_config, ConfigError
from src.data_feed import DataFeedError
from src.universe import UniverseError
from src.scheduler import run_scan
from src import output


def run_once(config):
    """One full cycle: fetch -> calculate -> score -> display."""
    top, all_scored = run_scan(config)
    output.render(top, config, scanned_count=len(all_scored))
    return top


def main():
    run_once_only = "--once" in sys.argv

    try:
        config = load_config()
    except ConfigError as e:
        print(f"\nConfiguration problem:\n  {e}\n")
        return 1

    minutes = config["schedule"]["refresh_minutes"]

    if run_once_only:
        try:
            run_once(config)
        except (DataFeedError, UniverseError, NotImplementedError) as e:
            print(f"\nData problem:\n  {e}\n")
            return 1
        return 0

    print(f"\nStock screener started. Refreshing every {minutes} minutes.")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                run_once(config)
            except (DataFeedError, UniverseError, NotImplementedError) as e:
                print(f"\nSkipping this cycle - {e}\n")

            next_run = datetime.now().timestamp() + minutes * 60
            print(f"\n  Next refresh at "
                  f"{datetime.fromtimestamp(next_run).strftime('%H:%M:%S')}\n")
            time.sleep(minutes * 60)
    except KeyboardInterrupt:
        print("\nStopped.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
