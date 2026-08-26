#!/usr/bin/env python3
"""Morning score dashboard. Reads the SQLite database read-only."""

import os
import sqlite3
from datetime import date, datetime, time, timedelta
import altair as alt
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

def make_36to60(score):
    return score/36*60

def score_chart(entries, key, max_score, height=220):
    """Bar chart where each bar takes its own colour from the gradient."""
    frame = pd.DataFrame([
        {
            "day": entry["day"].strftime("%d %b"),
            "score": entry[key] / max_score * 6,
            "colour": gradient_colour(entry[key], max_score),
        }
        for entry in entries
    ])
    return (
        alt.Chart(frame)
        .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2, size=14)
        .encode(
            x=alt.X(
                "day:N",
                sort=None,
                title=None,
                axis=alt.Axis(
                    labelColor=MUTED, labelAngle=-45, labelFontSize=10,
                    domainColor=EMPTY, tickColor=EMPTY,
                ),
            ),
            y=alt.Y(
                "score:Q",
                title=None,
                scale=alt.Scale(domain=[0, 6]),
                axis=alt.Axis(
                    labelColor=MUTED, labelFontSize=10,
                    grid=False, domain=False, ticks=False,
                ),
            ),
            color=alt.Color("colour:N", scale=None, legend=None),
            tooltip=[
                alt.Tooltip("day:N", title="Day"),
                alt.Tooltip("score:Q", title="Score", format=".1f"),
            ],
        )
        .properties(height=height)
        .configure_view(fill=None, stroke=None)
        .configure(background="transparent")
    )


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

def label_with_glyph(text, glyph):
    return (
        f'<div class="label-row"><span class="{glyph}"></span>'
        f'<div class="label">{text}</div></div>'
    )

st.set_page_config(page_title="Morning score", layout="centered")

st.markdown(f"""
<style>
    .stApp {{ background: {PAPER}; }}
    header, footer, #MainMenu {{ visibility: hidden; }}
    .block-container {{ padding-top: 2.5rem; max-width: 720px; }}
    h1, h2, h3, p, span, div {{ color: {INK}; }}
    
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

    .label-row {{
        display: flex;
        align-items: center;
        gap: 0.55rem;
        margin-bottom: 0.3rem;
    }}
    .label-row .label {{ margin-bottom: 0; }}

    .sun, .moon {{
        position: relative;
        width: 13px;
        height: 13px;
        flex: none;
        border-radius: 50%;
        opacity: 0.6;
    }}

    .sun {{
        background: radial-gradient(circle at 35% 32%, #C98A3C, #A26A34);
        box-shadow: 0 0 0 3px rgba(201, 138, 60, 0.13),
                    0 0 9px 2px rgba(201, 138, 60, 0.20);
    }}

    .moon {{
        background: {FILLED};
        box-shadow: 0 0 9px 2px rgba(47, 107, 95, 0.18);
    }}

    .moon::after {{
        content: "";
        position: absolute;
        top: -2px;
        left: 3.5px;
        width: 13px;
        height: 13px;
        border-radius: 50%;
        background: {PAPER};
    }}
    
    [data-testid="stVegaLiteChart"],
    [data-testid="stVegaLiteChart"] > div,
    [data-testid="stVegaLiteChart"] canvas,
    [data-testid="stArrowVegaLiteChart"],
    [data-testid="stArrowVegaLiteChart"] > div,
    .vega-embed, .vega-embed canvas, .vega-embed svg {{
        background: transparent !important;
    }}
</style>
""", unsafe_allow_html=True)

days = load_days()
score, state = live_score_today(days)

st.markdown(label_with_glyph("This morning", "sun"), unsafe_allow_html=True)
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
    st.altair_chart(score_chart(recent, "score", MAX_SCORE), use_container_width=True)

else:
    st.info("No finished days yet. Come back tomorrow.")

st.divider()


evening_score, evening_state = live_evening_score(days)

st.markdown(label_with_glyph("This evening", "moon"), unsafe_allow_html=True)
st.markdown(
    f'<div class="headline">{fmt_score(make_36to60(evening_score))}'
    f'<span style="color:{MUTED};font-size:1.5rem">'
    f' / {fmt_score(make_36to60(EVENING_MAX_SCORE))}</span></div>',
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
    left.metric("Average", fmt_score(make_36to60(average)))
    middle.metric("Best", fmt_score(make_36to60(best)))
    right.metric("Streak over 2.7", evening_streak(evenings_done, 27))

    st.markdown('<div class="label">Last 30 evenings</div>', unsafe_allow_html=True)
    recent = evenings_done[-30:]
    st.altair_chart(
        score_chart(recent, "evening_score", EVENING_MAX_SCORE),
        use_container_width=True,
    )
else:
    st.info("No finished evenings yet. Come back tomorrow.")