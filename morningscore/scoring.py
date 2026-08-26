"""Scoring rules shared by server.py and dashboard.py."""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import (WINDOW_START, WINDOW_END, SLOT_MINUTES, MAX_SCORE,
                    EVENING_WINDOW_START, EVENING_WINDOW_END,
                    EVENING_SLOT_MINUTES, EVENING_MAX_SCORE)

TZ = ZoneInfo(os.environ.get("SCORE_TZ", "Europe/Zurich"))


def window_start_on(day):
    return datetime.combine(day, WINDOW_START, tzinfo=TZ)


def window_end_on(day):
    return datetime.combine(day, WINDOW_END, tzinfo=TZ)


def in_window(moment):
    return window_start_on(moment.date()) <= moment < window_end_on(moment.date())


def score_for(first_ping, day):
    if first_ping is None:
        return MAX_SCORE
    minutes = (first_ping - window_start_on(day)).total_seconds() / 60
    return max(0, min(int(minutes // SLOT_MINUTES), MAX_SCORE))


def evening_start_on(day):
    return datetime.combine(day, EVENING_WINDOW_START, tzinfo=TZ)


def evening_end_on(day):
    extra = 1 if EVENING_WINDOW_END <= EVENING_WINDOW_START else 0
    return datetime.combine(day + timedelta(days=extra), EVENING_WINDOW_END, tzinfo=TZ)


def evening_day_for(moment):
    day = moment.date()
    return day if evening_start_on(day) <= moment else day - timedelta(days=1)


def current_evening_day(moment):
    """The evening in progress, or tonight's if the last one is over."""
    day = evening_day_for(moment)
    return day if moment < evening_end_on(day) else moment.date()


def in_evening_window(moment):
    day = evening_day_for(moment)
    return evening_start_on(day) <= moment < evening_end_on(day)


def evening_score_for(last_ping, day):
    if last_ping is None:
        return EVENING_MAX_SCORE
    minutes = (evening_end_on(day) - last_ping).total_seconds() / 60
    return max(0, min(int(minutes // EVENING_SLOT_MINUTES), EVENING_MAX_SCORE))