"""Scoring rules shared by server.py and dashboard.py."""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import (WINDOW_START, WINDOW_END, SLOT_MINUTES, MAX_SCORE,
                    EVENING_WINDOW_START, EVENING_WINDOW_END,
                    EVENING_SLOT_MINUTES, EVENING_MAX_SCORE)

TZ = ZoneInfo(os.environ.get("SCORE_TZ", "Europe/Zurich"))


from config import (DAY_WINDOW_START, DAY_WINDOW_END,
                    DAY_SLOT_MINUTES, DAY_MAX_SCORE)


def day_start_on(day):
    return datetime.combine(day, DAY_WINDOW_START, tzinfo=TZ)


def day_end_on(day):
    return datetime.combine(day, DAY_WINDOW_END, tzinfo=TZ)


def in_day_window(moment):
    return day_start_on(moment.date()) <= moment < day_end_on(moment.date())


def day_slots_elapsed(moment, day):
    """How many slots of that day are over already, clamped to the window."""
    if moment < day_start_on(day):
        return 0
    if moment >= day_end_on(day):
        return DAY_MAX_SCORE
    minutes = (moment - day_start_on(day)).total_seconds() // 60
    return int(minutes // DAY_SLOT_MINUTES)


def day_slot_for(moment):
    """Index of the slot a moment falls into, 0 .. DAY_MAX_SCORE - 1."""
    return day_slots_elapsed(moment, moment.date())


def day_score_for(busy_slots):
    """One point per quiet slot. No heartbeats at all is a full score."""
    return DAY_MAX_SCORE - len(busy_slots)

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