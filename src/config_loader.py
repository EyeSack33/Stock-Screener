"""
config_loader.py
----------------
Reads config.yaml and hands the settings to the rest of the program.

This is the only file that knows where settings come from, so if you
ever change how settings are stored, this is the only file to edit.
"""

import os
import yaml

# Where config.yaml lives (one folder up from src/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")


class ConfigError(Exception):
    """Raised when the config file is missing or has bad values."""
    pass


def load_config(path=DEFAULT_CONFIG_PATH):
    """Read config.yaml, check it makes sense, return it as a dictionary."""
    if not os.path.exists(path):
        raise ConfigError(
            f"Could not find a config file at:\n  {path}\n"
            "Copy config.example.yaml to config.yaml and edit it."
        )

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    # A host like Render supplies secrets as environment variables, which
    # keeps them out of the files you upload to GitHub.
    # This must happen BEFORE validation, or a key that only exists in the
    # environment would be reported as missing.
    ds = config.setdefault("data_source", {})
    for env_name, key in [("ALPACA_API_KEY", "api_key"),
                          ("ALPACA_API_SECRET", "api_secret")]:
        value = os.environ.get(env_name)
        if value:
            ds[key] = value

    # The Finnhub key lives in the host's environment, same as Alpaca's
    finnhub = os.environ.get("FINNHUB_API_KEY")
    if finnhub:
        config.setdefault("ratings", {})["api_key"] = finnhub

    _validate(config)

    # config.yaml has to be committed for Render to read it, so a key
    # typed into that file is one accidental push away from being public.
    # Warn loudly rather than let it pass quietly.
    if config["data_source"].get("provider") == "alpaca":
        from_file = not os.environ.get("ALPACA_API_KEY")
        if from_file and config["data_source"].get("api_key"):
            print("", flush=True)
            print("  " + "!" * 56, flush=True)
            print("  WARNING: your Alpaca key is written in config.yaml.",
                  flush=True)
            print("  That file gets committed to GitHub. An Alpaca key can",
                  flush=True)
            print("  place trades, not just read prices.", flush=True)
            print("", flush=True)
            print("  Fine for testing on your own computer. Before you push,",
                  flush=True)
            print("  blank both values and set ALPACA_API_KEY and",
                  flush=True)
            print("  ALPACA_API_SECRET in your host instead.", flush=True)
            print("  " + "!" * 56, flush=True)
            print("", flush=True)

    config["_project_root"] = PROJECT_ROOT
    return config


def _validate(config):
    """Catch the most common mistakes and explain them in plain English."""
    if not config:
        raise ConfigError("config.yaml is empty.")

    for section in ["data_source", "universe", "schedule", "indicators",
                    "scoring", "output"]:
        if section not in config:
            raise ConfigError(f"config.yaml is missing the '{section}' section.")

    uni = config["universe"]
    source = uni.get("source", "list").lower()
    if source not in ("list", "sp500", "file"):
        raise ConfigError(
            f"universe source must be list, sp500, or file - not '{source}'."
        )
    if source == "list" and not uni.get("tickers"):
        raise ConfigError(
            "universe source is 'list' but no tickers are listed under it."
        )

    ind = config["indicators"]
    if ind["short_ma_days"] >= ind["long_ma_days"]:
        raise ConfigError(
            "short_ma_days must be smaller than long_ma_days "
            f"(got {ind['short_ma_days']} and {ind['long_ma_days']})."
        )

    scoring = config["scoring"]

    mode = scoring.get("mode", "dip").lower()
    if mode not in ("analyst", "dip", "momentum"):
        raise ConfigError(
            f"scoring mode must be 'analyst', 'dip' or 'momentum', not '{mode}'."
        )
    if mode == "analyst" and not config.get("ratings", {}).get("api_key"):
        raise ConfigError(
            "Analyst mode needs a Finnhub key.\n"
            "Get one free at https://finnhub.io and set FINNHUB_API_KEY\n"
            "in Render's Environment tab."
        )

    weights = scoring["weights"]
    known = {"dip_today", "dip_recent", "ma_distance", "ma_trend"}
    unknown = set(weights) - known
    if unknown:
        raise ConfigError(
            f"Unknown scoring weight(s): {', '.join(sorted(unknown))}. "
            f"Valid names are: {', '.join(sorted(known))}."
        )

    total = sum(weights.values())
    if abs(total - 1.0) > 0.001:
        raise ConfigError(
            f"Your scoring weights add up to {total}, but they must add up to 1.0."
        )

    if ind.get("lookback_days", 3) < 1:
        raise ConfigError("lookback_days must be at least 1.")

    provider = config["data_source"]["provider"].lower()
    if provider not in ("yfinance", "alpaca", "mock"):
        raise ConfigError(
            f"provider must be 'yfinance', 'alpaca' or 'mock', not '{provider}'."
        )

    if provider == "alpaca":
        missing = [k for k in ("api_key", "api_secret")
                   if not config["data_source"].get(k)]
        if missing:
            raise ConfigError(
                f"Alpaca needs {' and '.join(missing)}.\n"
                "Set them in config.yaml, or as the environment variables\n"
                "ALPACA_API_KEY and ALPACA_API_SECRET."
            )
