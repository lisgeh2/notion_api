#!/usr/bin/env python3
"""
Poll the tracking server from anywhere. Prints a one-line summary.

  ./check.py                       # human-readable
  ./check.py --json                # raw json
  ./check.py --quiet               # print nothing, exit 1 if offline (for cron)
  ./check.py --alert-after 60      # only treat as alarming after 60 min dark

Env: TRACK_URL (e.g. https://track.example.com), TRACK_TOKEN
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("TRACK_URL", "http://127.0.0.1:8080").rstrip("/")
TOKEN = os.environ.get("TRACK_TOKEN", "")


def fetch(path, **params):
    params["token"] = TOKEN
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "phonetrack-check"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="phone")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--alert-after", type=float, default=0,
                    help="minutes of silence before exiting non-zero")
    args = ap.parse_args()

    try:
        data = fetch("/status", device=args.device)
    except urllib.error.HTTPError as e:
        print(f"server said {e.code} — check TRACK_TOKEN", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"cannot reach {BASE}: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(data, indent=2))
    elif not args.quiet:
        state = data.get("state")
        if state == "online":
            batt = data.get("battery")
            batt = f", {batt}%" if batt is not None else ""
            print(f"ONLINE  {data['minutes_ago']} min ago{batt}  "
                  f"{data.get('lat')},{data.get('lon')}")
            print(f"        {data.get('map_url', '')}")
        elif state == "offline":
            print(f"OFFLINE  dark for {data['minutes_ago']} min")
            print(f"         {data.get('detail', '')}")
            print(f"         last position: {data.get('map_url', 'unknown')}")
        else:
            print(f"UNKNOWN  {data.get('detail', '')}")

    if data.get("state") != "online":
        if data.get("minutes_ago", 1e9) >= args.alert_after:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
