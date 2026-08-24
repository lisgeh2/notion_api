# phonetrack

Your phone POSTs its location to your server every few minutes. "Is it off?" becomes
"have I heard from it recently?" — which is the only reliable proxy you can get without
Google's (nonexistent) public Find My Device API.

Files: `server.py` (the endpoint), `check.py` (client), `phonetrack.service` (systemd).

---

## 1. Server

```bash
sudo useradd --system --no-create-home phonetrack
sudo mkdir -p /opt/phonetrack /var/lib/phonetrack
sudo cp server.py /opt/phonetrack/
sudo python3 -m venv /opt/phonetrack/venv
sudo /opt/phonetrack/venv/bin/pip install flask waitress
sudo chown -R phonetrack:phonetrack /opt/phonetrack /var/lib/phonetrack

# secret goes in its own file — systemd units are world-readable
printf 'TRACK_TOKEN=%s\n' "$(openssl rand -hex 24)" | sudo tee /etc/phonetrack.env
sudo chmod 600 /etc/phonetrack.env

sudo cp phonetrack.service /etc/systemd/system/
sudo systemctl enable --now phonetrack
sudo systemctl status phonetrack
```

Note your token — you need it on the phone: `sudo cat /etc/phonetrack.env`

The service binds to `127.0.0.1` only. Terminate TLS in front of it.

## 2. TLS

The token travels in the URL, so plain HTTP would leak it to anyone on the path.

**Caddy** (gets a cert automatically):

```
track.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

**Or skip the public internet entirely** — install Tailscale on both the server and the
phone, and use the server's `100.x.y.z` address. No open ports, no cert, no exposure.
For a personal tracker this is the better default.

## 3. Phone: GPSLogger

Install GPSLogger (F-Droid or Play Store). Then:

- **Logging details → Log to custom URL** → on
- **URL:**

```
https://track.example.com/loc?token=YOUR_TOKEN&lat=%LAT&lon=%LON&batt=%BATT&acc=%ACC&alt=%ALT&spd=%SPD&time=%TIMESTAMP&prov=%PROV
```

- **HTTP method:** GET
- **Performance → Logging interval:** 300s is a sane balance. Below 60s eats battery.
- **Performance → Distance filter:** 0, so it still reports while stationary. That's what
  makes the heartbeat work — a filtered-out ping looks identical to a dead phone.
- **General → Start on bootup:** on

Grant location permission as **Allow all the time**, not "only while using".

## 4. Xiaomi / MIUI — do not skip this

MIUI is aggressive about killing background apps, and it is the single most common reason
these setups quietly stop reporting. For GPSLogger:

- Settings → Apps → Manage apps → GPSLogger → **Autostart: on**
- Same screen → **Battery saver → No restrictions**
- Settings → Battery → **turn off "Battery saver" / adaptive battery** for this app
- Open recents, swipe down on the GPSLogger card → **padlock icon** (survives "clear all")
- Settings → Apps → Permissions → **Display pop-up windows while running in background: on**

After setup, leave the phone alone for a few hours and check `/history`. If the gaps are
regular and long, MIUI is still killing it — recheck the list above.

## 5. Using it

```bash
export TRACK_URL=https://track.example.com
export TRACK_TOKEN=...

./check.py                # ONLINE  2.1 min ago, 87%  47.2977,8.8437
./check.py --json
./check.py --quiet --alert-after 45; echo $?   # 1 = dark for 45+ min
```

Endpoints, all requiring the token:

| Route | Purpose |
|---|---|
| `/loc` | ingest (GET or POST; also accepts a JSON body) |
| `/status` | last position + online/offline verdict |
| `/history?hours=24` | recent points as JSON |
| `/healthz` | no auth, for uptime monitoring |

Cron alert — mail yourself if the phone has been dark over an hour:

```cron
*/15 * * * * /path/check.py --quiet --alert-after 60 || echo "phone dark" | mail -s "phonetrack" you@example.com
```

## Reading the verdict honestly

`offline` means *the server stopped hearing from it*. That covers powered off, dead
battery, airplane mode, no coverage, and MIUI killing the app — and it cannot tell them
apart. The battery hint in `/status` is a guess based on the last reading, nothing more.

If the phone is stolen, a thief who powers it off ends your data at that moment. The last
known position is still the useful thing, and it's the same limit Find My Device has.
Keep Find My Device enabled too — it can ring and wipe, which this cannot.

## Housekeeping

SQLite grows by roughly a few MB per year at 5-minute intervals. To prune:

```bash
sqlite3 /var/lib/phonetrack/phonetrack.db \
  "DELETE FROM pings WHERE received_at < datetime('now','-180 days'); VACUUM;"
```
