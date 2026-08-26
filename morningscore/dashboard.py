#!/usr/bin/env python3
"""Morning score dashboard. Reads the SQLite database read-only."""

import os
import sqlite3
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from colors import INK, PAPER, MUTED, FILLED, EMPTY, GRADIENT
from config import (WINDOW_START, WINDOW_END, SLOT_MINUTES, MAX_SCORE,
                    EVENING_WINDOW_START, EVENING_WINDOW_END,
                    EVENING_SLOT_MINUTES, EVENING_MAX_SCORE)

import pandas as pd
import streamlit as st
from scoring import (TZ, window_start_on, window_end_on, in_window, score_for,
                     evening_start_on, evening_end_on, evening_day_for,
                     current_evening_day, in_evening_window, evening_score_for)

# Same rules as server.py. If you change them there, change them here.


DB_PATH = os.environ.get("SCORE_DB", "/var/lib/morningscore/morningscore.db")



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
        try:
            last_pings = {
                row["day"]: datetime.fromisoformat(row["last_ping"])
                for row in connection.execute("SELECT day, last_ping FROM evenings")
            }
        except sqlite3.OperationalError:
            last_pings = {}
        row = connection.execute(
            "SELECT value FROM meta WHERE key = 'start_day'"
        ).fetchone()
        start = date.fromisoformat(row["value"]) if row else date.today()
    today = datetime.now(TZ).date()
    days = []
    current = start
    while current <= today:
        first_ping = pings.get(current.isoformat())
        last_ping = last_pings.get(current.isoformat())
        days.append({
            "day": current,
            "first_ping": first_ping,
            "score": score_for(first_ping, current),
            "last_ping": last_ping,
            "evening_score": evening_score_for(last_ping, current),
        })
        current += timedelta(days=1)
    return days

def fmt_score(score):
    return f"{score / 10:.1f}"


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

def live_evening_score(days):
    now = datetime.now(TZ)
    day = current_evening_day(now)
    entry = next((e for e in days if e["day"] == day), None)
    last_ping = entry["last_ping"] if entry else None
    score = evening_score_for(last_ping, day)

    if last_ping is not None:
        return score, "phone last on at " + last_ping.strftime("%H:%M")
    if now < evening_start_on(day):
        return score, "evening has not started"
    return score, "still quiet"


def evening_streak(entries, threshold):
    streak = 0
    for entry in reversed(entries):
        if entry["evening_score"] >= threshold:
            streak += 1
        else:
            break
    return streak

def current_streak(days, threshold):
    streak = 0
    for entry in reversed(days[:-1]):
        if entry["score"] >= threshold:
            streak += 1
        else:
            break
    return streak


def gradient_colour(score, max_score):
    """Map any score onto the full gradient, so a perfect evening looks like a perfect morning."""
    return GRADIENT[round(score / max_score * (len(GRADIENT) - 1))]


def slot_grid(score, max_score, start_hour, slot_minutes, fill_from_end=False):
    """One block per slot. Filled = phone off."""
    blocks = []
    colour = gradient_colour(score, max_score)
    for index in range(max_score):
        filled = index >= max_score - score if fill_from_end else index < score
        minutes_in = index * slot_minutes
        hour = (start_hour + minutes_in // 60) % 24
        minute = minutes_in % 60
        blocks.append(
            f'<div class="slot" style="background:{colour if filled else EMPTY}" '
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
    f'<div class="headline">{fmt_score(score)}<span style="color:{MUTED};font-size:1.5rem">'
    f' / {fmt_score(MAX_SCORE)}</span></div>',
    unsafe_allow_html=True,
)
st.markdown(f'<div class="sub">{state}</div>', unsafe_allow_html=True)
st.markdown(slot_grid(score, MAX_SCORE, 8, SLOT_MINUTES), unsafe_allow_html=True)

finished = days[:-1]
if finished:
    average = sum(entry["score"] for entry in finished) / len(finished)
    best = max(entry["score"] for entry in finished)
    left, middle, right = st.columns(3)
    left.metric("Average", fmt_score(average))
    middle.metric("Best", fmt_score(best))
    right.metric("Streak over 4.5", current_streak(days, 45))

    st.markdown('<div class="label">Last 30 days</div>', unsafe_allow_html=True)
    recent = finished[-30:]
    st.bar_chart(
        pd.DataFrame(
            {"score": [entry["score"]/10 for entry in recent]},
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
            "Score": entry["score"]/10,
        }
        for entry in reversed(finished[-14:])
    ])
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={"Score": st.column_config.NumberColumn(format="%.1f")},
    )
else:
    st.info("No finished days yet. Come back tomorrow.")

st.markdown("---")

evening_score, evening_state = live_evening_score(days)

st.markdown('<div class="label">This evening</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="headline">{fmt_score(evening_score)}'
    f'<span style="color:{MUTED};font-size:1.5rem">'
    f' / {fmt_score(EVENING_MAX_SCORE)}</span></div>',
    unsafe_allow_html=True,
)
st.markdown(f'<div class="sub">{evening_state}</div>', unsafe_allow_html=True)
st.markdown(
    slot_grid(evening_score, EVENING_MAX_SCORE, 22, EVENING_SLOT_MINUTES,
              fill_from_end=True),
    unsafe_allow_html=True,
)

live_evening_day = current_evening_day(datetime.now(TZ))
evenings_done = [entry for entry in days if entry["day"] < live_evening_day]

if evenings_done:
    average = sum(entry["evening_score"] for entry in evenings_done) / len(evenings_done)
    best = max(entry["evening_score"] for entry in evenings_done)
    left, middle, right = st.columns(3)
    left.metric("Average", fmt_score(average))
    middle.metric("Best", fmt_score(best))
    right.metric("Streak over 2.7", evening_streak(evenings_done, 27))

    st.markdown('<div class="label">Last 30 evenings</div>', unsafe_allow_html=True)
    recent = evenings_done[-30:]
    st.bar_chart(
        pd.DataFrame(
            {"score": [entry["evening_score"]/10 for entry in recent]},
            index=[entry["day"].strftime("%d %b") for entry in recent],
        ),
        color=FILLED,
        height=220,
    )

    st.markdown('<div class="label">Last putdown</div>', unsafe_allow_html=True)
    table = pd.DataFrame([
        {
            "Day": entry["day"].strftime("%a %d %b"),
            "Last putdown": entry["last_ping"].strftime("%H:%M") if entry["last_ping"] else "never",
            "Score": entry["evening_score"]/10,
        }
        for entry in reversed(evenings_done[-14:])
    ])
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={"Score": st.column_config.NumberColumn(format="%.1f")},
    )
else:
    st.info("No finished evenings yet. Come back tomorrow.")