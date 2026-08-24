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

DAYS_AHEAD = 7
DAYS_BACK = 93

import unicodedata

import os
from dotenv import load_dotenv

load_dotenv()

ICS_URL = os.environ["ICS_URL"]

def get_friends(table):
    """Fetch every name from Friend DB's title column."""
    response = requests.post(f"{API}/data_sources/{table}/query", headers=HEADERS, json={})
    response.raise_for_status()

    names = []
    for row in response.json()["results"]:
        title = row["properties"][FRIEND_NAME]["title"]
        if title:
            names.append(title[0]["plain_text"])

    return names

def clean(name):
    """Lowercase and strip accents, so 'Céline' and 'celine' match."""
    stripped = unicodedata.normalize("NFD", name.strip().lower())
    if stripped in ["squacotreff", "squaco"]:
        return "squacos"
    if stripped in ["pflanze"]:
        return "plants"
    plain = "".join(c for c in stripped if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


def find_friend(name):
    return LOOKUP.get(clean(name))


def as_date(value):
    """DTSTART is a date for all-day events, a datetime otherwise."""
    return value.date() if hasattr(value, "hour") else value

def get_events(days_back=DAYS_BACK, days_ahead=DAYS_AHEAD):
    ics = requests.get(ICS_URL).text
    calendar = icalendar.Calendar.from_ical(ics)

    today = date.today()
    start, end = today - timedelta(days=days_back), today + timedelta(days=days_ahead)

    events = recurring_ical_events.of(calendar).between(start, end)
    events = [e for e in events if start <= as_date(e["DTSTART"].dt) <= end]

    return sorted(events, key=lambda e: as_date(e["DTSTART"].dt))



import os
 
import requests
 
FRIENDS_DB = "3c61034608be80339ccecf4abb888d1e"
HANGOUTS_DB = "3c61034608be8029a388c6edc708c92c"
 
# Rename these if your Notion columns are called something else.
FRIEND_NAME = "Name"      # title column on Friend DB
HANGOUT_NAME = "Name"     # title column on Hangouts
HANGOUT_DATE = "Date"     # date column on Hangouts
HANGOUT_FRIEND = "Friend" # relation column on Hangouts pointing at Friend DB
API = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"""Bearer {os.environ["NOTION_TOKEN"]}""",
    "Notion-Version": "2025-09-03",
    "Content-Type": "application/json",
}
 
 
def get_table(database_id):
    """A Notion database is a container. Writes need the table inside it."""
    response = requests.get(f"{API}/databases/{database_id}", headers=HEADERS)
    response.raise_for_status()
    return response.json()["data_sources"][0]["id"]
 
def find_friend_id(table, name):
    """Look up a friend row by its title, return the page ID or None."""
    body = {"filter": {"property": FRIEND_NAME, "title": {"equals": name}}}
    response = requests.post(f"{API}/data_sources/{table}/query", headers=HEADERS, json=body)
    response.raise_for_status()

    rows = response.json()["results"]
    return rows[0]["id"] if rows else None


def hangout_exists(table, title, when, friend_id):
    body = {"filter": {"and": [
        {"property": HANGOUT_NAME, "title": {"equals": title}},
        {"property": HANGOUT_DATE, "date": {"equals": when}},
        {"property": HANGOUT_FRIEND, "relation": {"contains": friend_id}},
    ]}}
    response = requests.post(f"{API}/data_sources/{table}/query", headers=HEADERS, json=body)
    response.raise_for_status()
    return bool(response.json()["results"])


def add_hangout(table, friend_id, title, when):
    body = {
        "parent": {"type": "data_source_id", "data_source_id": table},
        "properties": {
            HANGOUT_NAME: {"title": [{"text": {"content": title}}]},
            HANGOUT_DATE: {"date": {"start": when}},
            HANGOUT_FRIEND: {"relation": [{"id": friend_id}]},
        },
    }
    response = requests.post(f"{API}/pages", headers=HEADERS, json=body)
    response.raise_for_status()


def main():
    friends_table = get_table(FRIENDS_DB)
    hangouts_table = get_table(HANGOUTS_DB)

    global LOOKUP
    LOOKUP = {clean(name): name for name in get_friends(friends_table)}

    events = get_events()
    print(f"\nNext {DAYS_AHEAD} days — {len(events)} events\n")

    for event in events:
        start = event["DTSTART"].dt
        title = event.get("SUMMARY", "(no title)")

        if hasattr(start, "hour"):
            when = f"{start:%a %d %b  %H:%M}"
        else:
            when = f"{start:%a %d %b}  all day"

        for name in title.split(" "):
            result = find_friend(name)
            if not result:
                continue

            friend_id = find_friend_id(friends_table, result)
            if not friend_id:
                print(f"  '{result}' is in FRIENDS but not in Notion — skipped")
                continue

            iso = start.isoformat()
            if hangout_exists(hangouts_table, str(title), iso, friend_id):
                print(f"  {when:20} {title}  (already there)")
            else:
                add_hangout(hangouts_table, friend_id, str(title), iso)
                print(f"  {when:20} {title}  -> added")
    print()


if __name__ == "__main__":
    main()
