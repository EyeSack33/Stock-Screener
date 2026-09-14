#!/bin/bash
# Double-click this file to start the screener on a Mac.
# The first run takes a couple of minutes while it installs things.

cd "$(dirname "$0")" || exit 1

echo "==================================================="
echo "  Dip Screener"
echo "==================================================="
echo

# Find a working Python
PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "Python is not installed."
    echo
    echo "Download it from https://www.python.org/downloads/"
    echo "then double-click this file again."
    echo
    read -r -p "Press Enter to close."
    exit 1
fi

echo "Using $($PY --version)"
echo

# Install the packages only if they are missing
if ! $PY -c "import flask, yfinance, yaml" >/dev/null 2>&1; then
    echo "First run: installing Flask and yfinance. This takes a minute..."
    echo
    $PY -m pip install --quiet --upgrade pip
    if ! $PY -m pip install --quiet -r requirements.txt; then
        echo
        echo "The install failed. Check your internet connection."
        read -r -p "Press Enter to close."
        exit 1
    fi
    echo "Done installing."
    echo
fi

# Open the browser a few seconds after the server starts
( sleep 4; open "http://localhost:8000" ) &

echo "Starting up. Your browser will open by itself."
echo "The page says 'Scanning the market' for up to a minute - that is normal."
echo
echo "To stop: close this window, or press Control+C."
echo

$PY serve.py

echo
read -r -p "Stopped. Press Enter to close."
