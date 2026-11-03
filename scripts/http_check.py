#!/usr/bin/env python3
"""Wait until an HTTP endpoint answers 200, with strict timeouts.

Every single request has its own timeout (--request-timeout) and the whole
wait has a deadline (--timeout), so a hanging service can never block the
pipeline forever. Optionally checks a JSON field, e.g. --expect commit=<sha>.

Exit codes: 0 - healthy, 1 - not healthy before the deadline.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def probe(url: str, request_timeout: float) -> tuple[int | None, str]:
    """Perform one GET request. Returns (status, body) or (None, error text)."""
    try:
        with urllib.request.urlopen(url, timeout=request_timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:  # 4xx/5xx still carry a useful body
        return exc.code, exc.read().decode(errors="replace")
    except (urllib.error.URLError, OSError) as exc:
        return None, str(getattr(exc, "reason", exc))


def expectation_met(body: str, expect: list[str]) -> bool:
    """All KEY=VALUE pairs must match top-level fields of the JSON body."""
    if not expect:
        return True
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return False
    return all(str(data.get(k)) == v for k, v in (item.split("=", 1) for item in expect))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--timeout", type=float, default=60, help="overall deadline, s")
    parser.add_argument("--interval", type=float, default=2, help="pause between attempts, s")
    parser.add_argument("--request-timeout", type=float, default=3, help="per-request timeout, s")
    parser.add_argument("--expect", action="append", default=[], metavar="KEY=VALUE")
    args = parser.parse_args()

    deadline = time.monotonic() + args.timeout
    attempt = 0
    while True:
        attempt += 1
        status, body = probe(args.url, args.request_timeout)
        short = body.replace("\n", " ")[:160]
        if status == 200 and expectation_met(body, args.expect):
            print(f"[http-check] OK  {args.url} -> {status} (attempt {attempt}) {short}")
            return 0
        print(f"[http-check] ... {args.url} -> {status or 'no response'} (attempt {attempt}) {short}")
        if time.monotonic() + args.interval > deadline:
            print(f"[http-check] FAIL {args.url} not healthy after {args.timeout:.0f}s", file=sys.stderr)
            return 1
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
