"""
check_alpaca.py
---------------
Tests your Alpaca key against Alpaca directly, using nothing from the
rest of this project. If this works, your key is fine and the problem is
in the screener. If this fails, the problem is the key or the account.

    python check_alpaca.py

It asks for your key and secret and does not save them anywhere.
"""

import getpass
import sys


def main():
    print()
    print("=" * 60)
    print("  Alpaca key checker")
    print("=" * 60)
    print()
    print("Paste your key and secret. Nothing is saved.")
    print()

    key = input("Key ID      : ").strip()
    secret = getpass.getpass("Secret Key  : ").strip()

    if not key or not secret:
        print("\nBoth values are needed.\n")
        return 1

    print()
    from src import alpaca_check
    for line in alpaca_check.run(key, secret):
        print("  " + line)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
