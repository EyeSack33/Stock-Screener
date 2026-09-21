"""
net.py
------
Network plumbing that the rest of the app leans on.

Three tools:

  force_ipv4()          Makes outbound connections use IPv4 only.
  run_with_deadline()   Runs a function with a hard wall-clock limit.
  probe()               Tests the network step by step, for /net.

Why force IPv4?
  Some hosts advertise IPv6 but cannot actually route it. When a name
  like data.alpaca.markets resolves to several IPv6 addresses, Python
  tries each in turn and waits the full timeout on every one before
  falling back to IPv4. The request looks hung. Restricting lookups to
  IPv4 skips the dead addresses entirely.

Why a separate deadline?
  Socket timeouts do not cover DNS lookups, which are a blocking system
  call. The only way to guarantee a request cannot hang for ever is to
  run it in its own thread and stop waiting after a fixed time.
"""

import socket
import ssl
import threading
import time

_original_getaddrinfo = socket.getaddrinfo
_ipv4_forced = False


def force_ipv4():
    """Restrict every outbound name lookup in this process to IPv4."""
    global _ipv4_forced
    if _ipv4_forced:
        return

    def ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        return _original_getaddrinfo(host, port, socket.AF_INET,
                                     type, proto, flags)

    socket.getaddrinfo = ipv4_only
    _ipv4_forced = True
    print("  Network: outbound connections restricted to IPv4", flush=True)


class DeadlineExceeded(Exception):
    pass


def run_with_deadline(seconds, fn, *args, **kwargs):
    """
    Run fn(*args) and give up after `seconds`, no matter what it is doing.

    The work happens on a background thread. If it overruns we stop
    waiting and raise DeadlineExceeded. The stuck thread is abandoned; it
    is marked as a daemon so it cannot keep the app from shutting down.
    """
    box = {}

    def work():
        try:
            box["value"] = fn(*args, **kwargs)
        except BaseException as e:           # hand every failure back
            box["error"] = e

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(seconds)

    if worker.is_alive():
        raise DeadlineExceeded(f"no result after {seconds}s")
    if "error" in box:
        raise box["error"]
    return box.get("value")


# ----------------------------------------------------------------------
#  probe() - backs the /net page
# ----------------------------------------------------------------------

def _timed(label, seconds, fn, lines):
    """Run one step. Returns (status, result) where status is ok/hung/fail."""
    started = time.time()
    try:
        result = run_with_deadline(seconds, fn)
        lines.append(f"  {label:<26} OK   {time.time() - started:5.2f}s")
        return "ok", result
    except DeadlineExceeded:
        lines.append(f"  {label:<26} HUNG >{seconds}s")
        return "hung", None
    except Exception as e:
        lines.append(f"  {label:<26} FAIL {type(e).__name__}: {str(e)[:60]}")
        return "fail", None


def probe(host="data.alpaca.markets", port=443):
    """
    Walk through a connection one layer at a time. Every step has its own
    short deadline, so the whole thing always finishes in under a minute.
    """
    lines = [f"Network check for {host}", "=" * 54, ""]
    status = {}

    # 1. DNS, bypassing any IPv4 restriction so we see everything on offer
    lines.append("1. DNS lookup (every address the name resolves to)")
    status["dns"], infos = _timed(
        "resolve", 8,
        lambda: _original_getaddrinfo(host, port, 0, socket.SOCK_STREAM),
        lines)
    v4, v6 = [], []
    for family, _, _, _, addr in (infos or []):
        (v4 if family == socket.AF_INET else v6).append(addr[0])
    v4, v6 = list(dict.fromkeys(v4)), list(dict.fromkeys(v6))
    lines.append(f"     IPv4 addresses: {len(v4)}   IPv6 addresses: {len(v6)}")
    lines.append("")

    if status["dns"] != "ok":
        lines.append("What it means")
        lines.append("-" * 54)
        lines.append("  The server cannot look up names. Nothing further can")
        lines.append("  work until that is fixed, and the app cannot fix it.")
        lines.append("  Contact Render support.")
        return lines

    # 2. Raw TCP to each address family
    lines.append("2. Raw connection, no encryption")
    if v4:
        status["v4"], _ = _timed(
            f"IPv4 {v4[0]}", 8,
            lambda: socket.create_connection((v4[0], port), 7).close(), lines)
    else:
        lines.append("  no IPv4 address to try")
    if v6:
        status["v6"], _ = _timed(
            f"IPv6 {v6[0][:20]}", 8,
            lambda: socket.create_connection((v6[0], port), 7).close(), lines)
    lines.append("")

    # 3. A full HTTPS handshake over IPv4
    lines.append("3. Encrypted connection over IPv4")
    if v4 and status.get("v4") == "ok":
        def handshake():
            raw = socket.create_connection((v4[0], port), 7)
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(raw, server_hostname=host):
                pass
        status["tls"], _ = _timed("TLS handshake", 10, handshake, lines)
    else:
        lines.append("  skipped - IPv4 connection did not succeed")
    lines.append("")

    # Verdict, from the recorded results rather than the printed text
    lines.append("What it means")
    lines.append("-" * 54)
    if status.get("tls") == "ok":
        if status.get("v6") in ("hung", "fail"):
            lines.append("  IPv6 is broken on this server but IPv4 works.")
            lines.append("  That explains the stuck scans, and the app now")
            lines.append("  forces IPv4, so scans should complete.")
        else:
            lines.append("  The network is healthy. If scans still stall,")
            lines.append("  the problem is further up, not the connection.")
    elif status.get("v4") == "ok":
        lines.append("  A raw connection works but the encrypted handshake")
        lines.append("  does not. Something between Render and Alpaca is")
        lines.append("  interfering with HTTPS. Contact Render support.")
    else:
        lines.append("  IPv4 connections are not getting through. The host")
        lines.append("  is blocking or dropping outbound traffic, which the")
        lines.append("  app cannot work around. Contact Render support.")
    return lines
