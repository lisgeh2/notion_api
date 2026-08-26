#!/usr/bin/env python3
"""Morning score dashboard. Reads the SQLite database read-only."""

import os
import sqlite3
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from colors import INK, PAPER, MUTED, FILLED, EMPTY, GRADIENT
from config import WINDOW_START, WINDOW_END, SLOT_MINUTES, MAX_SCORE

import pandas as pd
import streamlit as st

# Same rules as server.py. If you change them there, change them here.


DB_PATH = os.environ.get("SCORE_DB", "/var/lib/morningscore/morningscore.db")
TZ = ZoneInfo(os.environ.get("SCORE_TZ", "Europe/Zurich"))



def read_db():
    connection = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


@st.cache_data(ttl=60)
def load_days():
    with read_db() as connection:
        pings = {
            row["day"]: datetime.fromisoformat(row["first_ping"])
            for row in connection.execute("SELECT day, first_ping FROM mornings")
        }
        row = connection.execute(
            "SELECT value FROM meta WHERE key = 'start_day'"
        ).fetchone()
        start = date.fromisoformat(row["value"]) if row else date.today()

    today = datetime.now(TZ).date()
    days = []
    current = start
    while current <= today:
        first_ping = pings.get(current.isoformat())
        days.append({
            "day": current,
            "first_ping": first_ping,
            "score": score_for(first_ping, current),
        })
        current += timedelta(days=1)
    return days


def window_start_on(day):
    return datetime.combine(day, WINDOW_START, tzinfo=TZ)


def score_for(first_ping, day):
    if first_ping is None:
        return MAX_SCORE
    minutes = (first_ping - window_start_on(day)).total_seconds() / 60
    return max(0, min(int(minutes // SLOT_MINUTES), MAX_SCORE))


def live_score_today(days):
    today = days[-1]
    now = datetime.now(TZ)
    if today["first_ping"] is not None:
        return today["score"], "phone came on at " + today["first_ping"].strftime("%H:%M")
    if now < window_start_on(today["day"]):
        return 0, "morning has not started"
    if now >= datetime.combine(today["day"], WINDOW_END, tzinfo=TZ):
        return MAX_SCORE, "untouched all morning"
    return score_for(now, today["day"]), "still going"


def current_streak(days, threshold):
    streak = 0
    for entry in reversed(days[:-1]):
        if entry["score"] >= threshold:
            streak += 1
        else:
            break
    return streak


def slot_grid(score):
    """Sixty blocks, one per five minutes of the morning. Filled = survived."""
    blocks = []
    for index in range(MAX_SCORE):
        colour = GRADIENT[score] if index < score else EMPTY
        hour = 8 + (index * SLOT_MINUTES) // 60
        minute = (index * SLOT_MINUTES) % 60
        blocks.append(
            f'<div class="slot" style="background:{colour}" '
            f'title="{hour:02d}:{minute:02d}"></div>'
        )
    return f'<div class="grid">{"".join(blocks)}</div>'


st.set_page_config(page_title="Morning score", layout="centered")

st.markdown(f"""
<style>
    .stApp {{ background: {PAPER}; }}
    header, footer, #MainMenu {{ visibility: hidden; }}
    .block-container {{ padding-top: 2.5rem; max-width: 720px; }}
    h1, h2, h3, p, span, div {{ color: {INK}; }}
    .grid {{
        display: flex;
        margin: 0.5rem 0 1.5rem 0;
    }}
    .grid {{
        display: flex;
        width: 100%;
        max-width: 480px;
        margin: 0.5rem 0 1.5rem 0;
    }}

    .grid > * {{
        flex: 1 1 0;
        min-width: 0;          /* lets blocks shrink below intrinsic size */
        height: 40px;
        border-right: 2px solid {PAPER};
    }}

    .grid > *:last-child {{
        border-right: none;
    }}

    .slot {{ border-radius: 2px; }}   /* aspect-ratio removed */
    .headline {{
        font-size: 4.5rem; font-weight: 700; line-height: 1;
        letter-spacing: -0.03em; margin-bottom: 0.2rem;
    }}
    .sub {{ color: {MUTED}; font-size: 0.95rem; margin-bottom: 1.5rem; }}
    .label {{
        color: {MUTED}; font-size: 0.75rem; text-transform: uppercase;
        letter-spacing: 0.1em; margin-bottom: 0.3rem;
    }}
</style>
""", unsafe_allow_html=True)

days = load_days()
score, state = live_score_today(days)

st.markdown('<div class="label">This morning</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="headline">{score}<span style="color:{MUTED};font-size:1.5rem">'
    f' / {MAX_SCORE}</span></div>',
    unsafe_allow_html=True,
)
st.markdown(f'<div class="sub">{state}</div>', unsafe_allow_html=True)
st.markdown(slot_grid(score), unsafe_allow_html=True)

finished = days[:-1]
if finished:
    average = sum(entry["score"] for entry in finished) / len(finished)
    best = max(entry["score"] for entry in finished)
    left, middle, right = st.columns(3)
    left.metric("Average", f"{average:.0f}")
    middle.metric("Best", best)
    right.metric("Streak over 24", current_streak(days, 24))

    st.markdown('<div class="label">Last 30 days</div>', unsafe_allow_html=True)
    recent = finished[-30:]
    st.bar_chart(
        pd.DataFrame(
            {"score": [entry["score"] for entry in recent]},
            index=[entry["day"].strftime("%d %b") for entry in recent],
        ),
        color=FILLED,
        height=220,
    )

    st.markdown('<div class="label">First pickup</div>', unsafe_allow_html=True)
    table = pd.DataFrame([
        {
            "Day": entry["day"].strftime("%a %d %b"),
            "First pickup": entry["first_ping"].strftime("%H:%M") if entry["first_ping"] else "never",
            "Score": entry["score"],
        }
        for entry in reversed(finished[-14:])
    ])
    st.dataframe(table, hide_index=True, width="stretch")
else:
    st.info("No finished days yet. Come back tomorrow.")
