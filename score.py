#!/usr/bin/env python3
"""
Show your morning scores.

    ./score.py            today
    ./score.py --history  last 14 days as a bar chart

Environment variables: SCORE_URL, SCORE_TOKEN
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = os.environ.get("SCORE_URL", "http://127.0.0.1:8080").rstrip("/")
TOKEN = os.environ.get("SCORE_TOKEN", "")


def get(path, **params):
    params["token"] = TOKEN
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.loads(response.read())


def show_today():
    data = get("/today")
    bar = "#" * (data["score"] // 2)
    print(f"\n  {data['score']} / {data['max_score']}   {bar}")
    print(f"  {data['state']}")
    if data["first_ping"]:
        print(f"  phone came on at {data['first_ping']}")
    print()


def show_history(days):
    data = get("/scores", days=days)
    print()
    for entry in data["days"]:
        bar = "#" * (entry["score"] // 2)
        when = entry["first_ping"] or "never"
        print(f"  {entry['day']}  {entry['score']:>2}  {bar:<30} {when}")
    if data["average"] is not None:
        print(f"\n  average: {data['average']} / {data['max_score']}")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()

    try:
        show_history(args.days) if args.history else show_today()
    except Exception as error:
        print(f"cannot reach {BASE}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
