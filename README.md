# Notion Friends CRM – Calendar Sync

A small personal CRM that keeps my **Notion friends database** up to date
automatically. It reads my Google Calendar, recognises which friends I met,
logs each meeting as a *hangout* in Notion and calculates when I should get in
touch with each friend again.

Runs on a schedule with **GitHub Actions**, so no server is needed.

## How it works

```
Google Calendar (iCal feeds)
        │  events from the last 93 days + next 7 days
        ▼
show_calendar.py ── matches words in event titles against friend names
        │
        ├──► Notion "Hangouts" database   new entry per meeting (title, date, friend relation)
        │                                 skipped if it already exists
        └──► Notion "Friends" database    Next contact = last contacted + time interval
```

1. **Load friends** – fetches all names from the Notion *Friends* database and
   builds a lookup that ignores case, accents and punctuation (`Céline` = `celine`),
   plus a few aliases.
2. **Read the calendar** – downloads two private iCal feeds (calendar + to-dos)
   and expands recurring events with `recurring-ical-events`.
3. **Match & log** – every word of an event title is compared with the friend
   list. For each match a *Hangout* page is created in Notion and linked to the
   friend. Existing entries are detected, so the sync is **idempotent** and can
   run as often as needed.
4. **Plan the next contact** – for each friend, Notion's rollup *last contacted*
   plus the friend's individual *time interval* (in days) gives the
   *Next contact* date, which is written back only if it changed.

## Notion setup

| Database | Column | Type |
|---|---|---|
| **Friends** | `Name` | Title |
| | `Time Intervall` | Number (days between contacts) |
| | `last contacted` | Rollup – latest `Date` of the related hangouts |
| | `Next contact` | Date (filled in by the script) |
| **Hangouts** | `Name` | Title |
| | `Date` | Date |
| | `Friend` | Relation → Friends |

Create a [Notion integration](https://www.notion.so/my-integrations), share both
databases with it and put the database IDs in `FRIENDS_DB` / `HANGOUTS_DB` in
`show_calendar.py`. Column names can be changed with the constants at the top of
the script.

## Configuration

| Variable | Description |
|---|---|
| `NOTION_TOKEN` | Notion integration secret |
| `ICS_URL` | Google Calendar → Settings → *Secret address in iCal format* |
| `ICS_URL_TODO` | a second iCal feed (e.g. a to-do calendar) |

Locally these are read from a `.env` file (git-ignored); in GitHub Actions they
are stored as repository secrets.

## Run locally

```bash
pip install -r requirements.txt
python show_calendar.py
```

Example output:

```
Next 7 days — 12 events

  Mon 20 Oct  18:30    Dinner Anna  -> added
  Wed 22 Oct  all day  Hike Tom     (already there)

Updating next contact dates

  Anna         next contact 2026-11-03
```

## Automation

[`.github/workflows/sync.yaml`](.github/workflows/sync.yaml) runs the sync five
times a day (and on demand via *Run workflow*) on GitHub's hosted runners.

## Tech

Python · Notion API · iCalendar · GitHub Actions
