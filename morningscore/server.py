#!/usr/bin/env python3
"""Morning score server. First ping between 08:00 and 13:00 sets the score."""

import hmac
import os
import sqlite3
import sys
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from config import (WINDOW_START, WINDOW_END, SLOT_MINUTES, MAX_SCORE,
                    EVENING_WINDOW_START, EVENING_WINDOW_END,
                    EVENING_SLOT_MINUTES, EVENING_MAX_SCORE)

from flask import Flask, g, jsonify, request


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

def evening_start_on(day):
    return datetime.combine(day, EVENING_WINDOW_START, tzinfo=TZ)


def evening_end_on(day):
    # window crosses midnight -> the end belongs to the following day
    extra = 1 if EVENING_WINDOW_END <= EVENING_WINDOW_START else 0
    return datetime.combine(day + timedelta(days=extra), EVENING_WINDOW_END, tzinfo=TZ)


def evening_day_for(moment):
    """A ping at 00:30 belongs to yesterday's evening."""
    day = moment.date()
    return day if evening_start_on(day) <= moment else day - timedelta(days=1)


def in_evening_window(moment):
    day = evening_day_for(moment)
    return evening_start_on(day) <= moment < evening_end_on(day)


def score_for(first_ping, day):
    if first_ping is None:
        return MAX_SCORE
    minutes_survived = (first_ping - window_start_on(day)).total_seconds() / 60
    return max(0, min(int(minutes_survived // SLOT_MINUTES), MAX_SCORE))

def evening_score_for(last_ping, day):
    if last_ping is None:
        return EVENING_MAX_SCORE
    minutes_early = (evening_end_on(day) - last_ping).total_seconds() / 60
    return max(0, min(int(minutes_early // EVENING_SLOT_MINUTES), EVENING_MAX_SCORE))

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
        conn.execute("""CREATE TABLE IF NOT EXISTS evenings (
                    day       TEXT PRIMARY KEY,
                    last_ping TEXT NOT NULL)""")


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

def save_last_ping(moment, day):
    db().execute(
        """INSERT INTO evenings (day, last_ping) VALUES (?, ?)
           ON CONFLICT(day) DO UPDATE SET last_ping = excluded.last_ping""",
        (day.isoformat(), moment.isoformat()),
    )
    db().commit()

def load_last_ping(day):
    row = db().execute("SELECT last_ping FROM evenings WHERE day = ?",
                       (day.isoformat(),)).fetchone()
    return datetime.fromisoformat(row["last_ping"]) if row else None


def authorized():
    supplied = request.args.get("token") or request.headers.get("X-Token", "")
    return bool(supplied) and hmac.compare_digest(supplied, TOKEN)


@app.route("/ping", methods=["GET", "POST"])
def ping():
    if not authorized():
        return jsonify(error="forbidden"), 403
    moment = now()

    if in_window(moment):
        day = moment.date()
        was_first = save_first_ping(moment)
        return jsonify(window="morning", recorded=was_first,
                       score=score_for(load_first_ping(day), day)), 200

    if in_evening_window(moment):
        day = evening_day_for(moment)
        save_last_ping(moment, day)
        return jsonify(window="evening", recorded=True,
                       score=evening_score_for(moment, day)), 200

    return jsonify(recorded=False, reason="outside scoring window"), 200

def current_evening_day(moment):
    """The evening in progress, or tonight's if it hasn't started."""
    day = evening_day_for(moment)
    return day if moment < evening_end_on(day) else moment.date()

@app.get("/today")
def today():
    if not authorized():
        return jsonify(error="forbidden"), 403
    moment = now()
    day = moment.date()
    
    # Morning
    
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
    
    
    #### evening
    
    evening_day = current_evening_day(moment)
    last_ping = load_last_ping(evening_day)

    if moment < evening_start_on(evening_day):
        e_state, e_final = "evening has not started yet", False
    elif moment < evening_end_on(evening_day):
        e_state = "phone still off" if last_ping is None else "phone was on"
        e_final = False
    else:
        e_state = "perfect evening, no ping at all" if last_ping is None else "phone was on"
        e_final = True

    return jsonify(
        day=day.isoformat(),
        score=score_for(first_ping, day) if first_ping else score_for(reference, day),
        max_score=MAX_SCORE,
        first_ping=first_ping.strftime("%H:%M") if first_ping else None,
        state=state,
        final=final,
        evening={
            "day": evening_day.isoformat(),
            "score": evening_score_for(last_ping, evening_day),
            "max_score": EVENING_MAX_SCORE,
            "last_ping": last_ping.strftime("%H:%M") if last_ping else None,
            "state": e_state,
            "final": e_final,
        },
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
        last_ping = load_last_ping(day)
        results.append({"day": day.isoformat(),
                        "score": score_for(first_ping, day),
                        "first_ping": first_ping.strftime("%H:%M") if first_ping else None,
                        "evening_score": evening_score_for(last_ping, day),
                        "last_ping": last_ping.strftime("%H:%M") if last_ping else None})
    finished = [r for r in results if r["day"] != today_date.isoformat()]
    average = round(sum(r["score"] for r in finished) / len(finished), 1) if finished else None
    evening_average = (round(sum(r["evening_score"] for r in finished) / len(finished), 1)
                       if finished else None)
    return jsonify(days=results, average=average, evening_average=evening_average,
                   max_score=MAX_SCORE, evening_max_score=EVENING_MAX_SCORE), 200

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
