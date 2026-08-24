"""
show_calendar.py — print my upcoming calendar events.

Setup:
    pip install requests icalendar recurring-ical-events

    In Google Calendar: Settings -> click your calendar in the left sidebar ->
    scroll to "Secret address in iCal format" -> paste it into ICS_URL below.

Run:
    python show_calendar.py
"""

from datetime import date, timedelta

import icalendar
import recurring_ical_events
import requests
import re

ICS_URL = """https://calendar.google.com/calendar/ical/lisa.gehrig2002%40gmail.com/private-25eae5269a4776b08d751cf4b0096aca/basic.ics"""
DAYS_AHEAD = 14

import unicodedata

FRIENDS = ["Anna", "Aaron", "Andreas", "Family", "Céline", "Ati", "Squacos", "Ferris"]

def clean(name):
    """Lowercase and strip accents, so 'Céline' and 'celine' match."""
    stripped = unicodedata.normalize("NFD", name.strip().lower())
    if stripped in ["squacotreff", "squaco"]:
        return "squacos"
    plain = "".join(c for c in stripped if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


LOOKUP = {clean(name): name for name in FRIENDS}


def find_friend(name):
    return LOOKUP.get(clean(name))
        
        


def get_events(days):
    ics = requests.get(ICS_URL).text
    calendar = icalendar.Calendar.from_ical(ics)

    today = date.today()
    events = recurring_ical_events.of(calendar).between(today, today + timedelta(days=days))

    return sorted(events, key=lambda e: str(e["DTSTART"].dt))


def main():
    events = get_events(DAYS_AHEAD)
    print(events)
    print(f"\nNext {DAYS_AHEAD} days — {len(events)} events\n")
    for event in events:
        start = event["DTSTART"].dt
        title = event.get("SUMMARY", "(no title)")
        # All-day events give a date object; timed events give a datetime.
        if hasattr(start, "hour"):
            when = f"{start:%a %d %b  %H:%M}"
        else:
            when = f"{start:%a %d %b}  all day"
        
        title_split_names = title.split(" ")
        for name in title_split_names:
            result = find_friend(name)
            if result:  
                print(result)
                print(f"  {when:20} {title}")
    print()


if __name__ == "__main__":
    main()
