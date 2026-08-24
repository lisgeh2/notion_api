#!/usr/bin/env python3
"""
Minimal phone-tracking endpoint for GPSLogger (or anything that can hit a URL).

Answers two questions:
  1. Where was the phone last seen?
  2. Is it still alive, or did it go dark (powered off / no signal / app killed)?

Config via environment variables:
  TRACK_TOKEN      shared secret, required        (default: refuses to start)
  TRACK_DB         sqlite file path               (default: ./phonetrack.db)
  TRACK_HOST       bind address                   (default: 127.0.0.1)
  TRACK_PORT       bind port                      (default: 8080)
  TRACK_STALE_MIN  minutes before "offline"       (default: 15)
"""

import hmac
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timedelta, timezone

from flask import Flask, g, jsonify, request

TOKEN = os.environ.get("TRACK_TOKEN", "")
DB_PATH = os.environ.get("TRACK_DB", "phonetrack.db")
HOST = os.environ.get("TRACK_HOST", "127.0.0.1")
PORT = int(os.environ.get("TRACK_PORT", "8080"))
STALE_MIN = int(os.environ.get("TRACK_STALE_MIN", "15"))

app = Flask(__name__)


# --------------------------------------------------------------------------- db

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                device      TEXT    NOT NULL DEFAULT 'phone',
                received_at TEXT    NOT NULL,
                device_time TEXT,
                lat         REAL,
                lon         REAL,
                accuracy    REAL,
                altitude    REAL,
                speed       REAL,
                battery     INTEGER,
                charging    TEXT,
                provider    TEXT,
                raw         TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_pings_device_time
                ON pings (device, received_at DESC);
            """
        )
        conn.commit()


# ---------------------------------------------------------------------- helpers

def now():
    return datetime.now(timezone.utc)


def authorized(req):
    """Token from ?token=, X-Token header, or Bearer auth. Constant-time compare."""
    supplied = (
        req.args.get("token")
        or req.headers.get("X-Token")
        or (req.headers.get("Authorization", "").removeprefix("Bearer ").strip())
    )
    return bool(supplied) and hmac.compare_digest(supplied, TOKEN)


def num(value, cast=float):
    """GPSLogger sends empty strings or literal '%BATT' when a value is missing."""
    if value is None:
        return None
    value = str(value).strip()
    if not value or value.startswith("%"):
        return None
    try:
        return cast(float(value))
    except (TypeError, ValueError):
        return None


def params(req):
    """Merge query string, form body and JSON body into one dict."""
    merged = dict(req.args)
    merged.update(req.form.to_dict())
    if req.is_json:
        payload = req.get_json(silent=True)
        if isinstance(payload, dict):
            merged.update({k: v for k, v in payload.items()})
    merged.pop("token", None)
    return merged


def classify(row):
    """Turn the last ping into a human verdict about the phone's state."""
    seen = datetime.fromisoformat(row["received_at"])
    age_min = (now() - seen).total_seconds() / 60

    if age_min < STALE_MIN:
        return "online", age_min, None

    battery = row["battery"]
    if battery is not None and battery <= 5:
        hint = f"last battery reading was {battery}% — probably ran flat"
    elif battery is not None and battery <= 20:
        hint = f"last battery reading was {battery}% — may have run flat"
    else:
        hint = "powered off, out of signal, or the logger app was killed by MIUI"
    return "offline", age_min, hint


# ----------------------------------------------------------------------- routes

@app.route("/loc", methods=["GET", "POST"])
def loc():
    if not authorized(request):
        return jsonify(error="forbidden"), 403

    p = params(request)
    row = (
        p.get("device") or p.get("id") or "phone",
        now().isoformat(),
        p.get("time") or p.get("timestamp"),
        num(p.get("lat") or p.get("latitude")),
        num(p.get("lon") or p.get("longitude")),
        num(p.get("acc") or p.get("accuracy")),
        num(p.get("alt") or p.get("altitude")),
        num(p.get("spd") or p.get("speed")),
        num(p.get("batt") or p.get("battery"), int),
        p.get("charging") or p.get("isCharging"),
        p.get("prov") or p.get("provider"),
        repr(p),
    )

    conn = db()
    conn.execute(
        """INSERT INTO pings
           (device, received_at, device_time, lat, lon, accuracy, altitude,
            speed, battery, charging, provider, raw)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        row,
    )
    conn.commit()
    return "ok", 200


@app.get("/status")
def status():
    if not authorized(request):
        return jsonify(error="forbidden"), 403

    device = request.args.get("device", "phone")
    row = db().execute(
        "SELECT * FROM pings WHERE device = ? ORDER BY received_at DESC LIMIT 1",
        (device,),
    ).fetchone()

    if row is None:
        return jsonify(device=device, state="unknown",
                       detail="no ping ever received"), 200

    state, age_min, hint = classify(row)
    body = {
        "device": device,
        "state": state,
        "minutes_ago": round(age_min, 1),
        "last_seen_utc": row["received_at"],
        "lat": row["lat"],
        "lon": row["lon"],
        "accuracy_m": row["accuracy"],
        "battery": row["battery"],
        "charging": row["charging"],
        "provider": row["provider"],
    }
    if row["lat"] is not None and row["lon"] is not None:
        body["map_url"] = f"https://www.google.com/maps?q={row['lat']},{row['lon']}"
    if hint:
        body["detail"] = hint
    return jsonify(body), 200


@app.get("/history")
def history():
    if not authorized(request):
        return jsonify(error="forbidden"), 403

    device = request.args.get("device", "phone")
    hours = max(1, min(int(request.args.get("hours", 24)), 24 * 90))
    limit = max(1, min(int(request.args.get("limit", 500)), 5000))
    since = (now() - timedelta(hours=hours)).isoformat()

    rows = db().execute(
        """SELECT received_at, lat, lon, accuracy, battery, charging, provider
           FROM pings
           WHERE device = ? AND received_at >= ?
           ORDER BY received_at DESC LIMIT ?""",
        (device, since, limit),
    ).fetchall()
    return jsonify(device=device, hours=hours, count=len(rows),
                   points=[dict(r) for r in rows]), 200


@app.get("/healthz")
def healthz():
    return "ok", 200


# ------------------------------------------------------------------------- main

if __name__ == "__main__":
    if len(TOKEN) < 16:
        sys.exit("TRACK_TOKEN is unset or shorter than 16 chars — refusing to start.")
    init_db()
    try:
        from waitress import serve
        print(f"waitress on {HOST}:{PORT} (db={DB_PATH}, stale={STALE_MIN}min)")
        serve(app, host=HOST, port=PORT, threads=4)
    except ImportError:
        print(f"waitress not installed, using flask dev server on {HOST}:{PORT}")
        app.run(host=HOST, port=PORT)
