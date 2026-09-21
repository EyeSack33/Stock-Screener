"""
http_worker.py
--------------
Makes exactly one web request, then exits. It runs as its own separate
program, launched by net.http_get_isolated().

Why a separate program?
  Inside the main app, three different kinds of timeout failed to stop
  stuck requests on the host. A request stuck inside the app cannot be
  forcibly stopped from outside it. A separate program can - the app
  simply kills it when time is up. Whatever goes wrong in here, the main
  app keeps running and gets a clear answer.

Reads a JSON job from standard input:
    {"url": "...", "headers": {...}, "timeout": 20}

Writes a JSON result to standard output:
    {"status": 200, "body": "..."}      on any HTTP response
    {"status": null, "body": "reason"}   if no response at all
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request


def main():
    job = json.loads(sys.stdin.read())

    # Test hook only: lets the test suite simulate a request that hangs.
    if os.environ.get("SCREENER_TEST_HANG"):
        time.sleep(3600)

    req = urllib.request.Request(job["url"], headers=job.get("headers", {}))
    try:
        with urllib.request.urlopen(req, timeout=job.get("timeout", 20)) as r:
            result = {"status": r.status,
                      "body": r.read().decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        result = {"status": e.code,
                  "body": e.read().decode("utf-8", "replace")}
    except Exception as e:
        result = {"status": None, "body": f"{type(e).__name__}: {e}"}

    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
