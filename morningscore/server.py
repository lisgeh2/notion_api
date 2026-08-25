#!/usr/bin/env python3
"""Morning score server. First ping between 08:00 and 13:00 sets the score."""

import hmac
import os
import sqlite3
import sys
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import Flask, g, jsonify, request

WINDOW_START = time(8, 0)
WINDOW_END = time(13, 0)
SLOT_MINUTES = 5
MAX_SCORE = 60

TOKEN = os.environ.get("SCORE_TOKEN", "")
DB_PATH = os.environ.get("SCORE_DB", "morningscore.db")
TZ = ZoneInfo(os.environ["SCORE_TZ"]) if "SCORE_TZ" in os.environ else None
HOST = os.environ.get("SCORE_HOST", "127.0.0.1")
PORT = int(os.environ.get("SCORE_PORT", "8080"))

app = Flask(__name__)


def now():
    return datetime.now(TZ)


def window_start_on(day):
    return datetime.combine(day, WINDOW_START, tzinfo=TZ)


def window_end_on(day):
    return datetime.combine(day, WINDOW_END, tzinfo=TZ)


def score_for(first_ping, day):
    if first_ping is None:
        return MAX_SCORE
    minutes_survived = (first_ping - window_start_on(day)).total_seconds() / 60
    return max(0, min(int(minutes_survived // SLOT_MINUTES), MAX_SCORE))


def in_window(moment):
    return window_start_on(moment.date()) <= moment < window_end_on(moment.date())


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exception):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS mornings (
                            day        TEXT PRIMARY KEY,
                            first_ping TEXT NOT NULL)""")
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('start_day', ?)",
                     (datetime.now(TZ).date().isoformat(),))


def start_day():
    row = db().execute("SELECT value FROM meta WHERE key = 'start_day'").fetchone()
    return datetime.fromisoformat(row["value"]).date()


def save_first_ping(moment):
    cursor = db().execute(
        "INSERT OR IGNORE INTO mornings (day, first_ping) VALUES (?, ?)",
        (moment.date().isoformat(), moment.isoformat()),
    )
    db().commit()
    return cursor.rowcount == 1


def load_first_ping(day):
    row = db().execute("SELECT first_ping FROM mornings WHERE day = ?",
                       (day.isoformat(),)).fetchone()
    return datetime.fromisoformat(row["first_ping"]) if row else None


def authorized():
    supplied = request.args.get("token") or request.headers.get("X-Token", "")
    return bool(supplied) and hmac.compare_digest(supplied, TOKEN)


@app.route("/ping", methods=["GET", "POST"])
def ping():
    if not authorized():
        return jsonify(error="forbidden"), 403
    moment = now()
    if not in_window(moment):
        return jsonify(recorded=False, reason="outside scoring window"), 200
    was_first = save_first_ping(moment)
    return jsonify(recorded=was_first,
                   score=score_for(load_first_ping(moment.date()), moment.date())), 200


@app.get("/today")
def today():
    if not authorized():
        return jsonify(error="forbidden"), 403
    moment = now()
    day = moment.date()
    first_ping = load_first_ping(day)

    if first_ping is not None:
        state, final = "phone was turned on", True
    elif moment < window_start_on(day):
        state, final = "morning has not started yet", False
    elif moment >= window_end_on(day):
        state, final = "perfect morning, no ping at all", True
    else:
        state, final = "still going, phone still off", False

    reference = first_ping if first_ping else min(moment, window_end_on(day))
    return jsonify(
        day=day.isoformat(),
        score=score_for(first_ping, day) if first_ping else score_for(reference, day),
        max_score=MAX_SCORE,
        first_ping=first_ping.strftime("%H:%M") if first_ping else None,
        state=state,
        final=final,
    ), 200


@app.get("/scores")
def scores():
    if not authorized():
        return jsonify(error="forbidden"), 403
    days_back = max(1, min(int(request.args.get("days", 30)), 365))
    today_date = now().date()
    first_tracked_day = start_day()
    results = []

    for offset in range(days_back):
        day = today_date - timedelta(days=offset)
        if day < first_tracked_day:
            break
        first_ping = load_first_ping(day)
        results.append({"day": day.isoformat(),
                        "score": score_for(first_ping, day),
                        "first_ping": first_ping.strftime("%H:%M") if first_ping else None})

    finished = [r for r in results if r["day"] != today_date.isoformat()]
    average = round(sum(r["score"] for r in finished) / len(finished), 1) if finished else None
    return jsonify(days=results, average=average, max_score=MAX_SCORE), 200


@app.get("/healthz")
def healthz():
    return "ok", 200


if __name__ == "__main__":
    if len(TOKEN) < 16:
        sys.exit("SCORE_TOKEN is missing or shorter than 16 characters.")
    init_db()
    try:
        from waitress import serve
        print(f"listening on {HOST}:{PORT}")
        serve(app, host=HOST, port=PORT, threads=4)
    except ImportError:
        app.run(host=HOST, port=PORT)
