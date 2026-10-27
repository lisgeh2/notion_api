# morningscore

Your phone sends "I'm alive" every 5 minutes. The server only keeps the **first**
ping between **08:00 and 13:00**. The longer you hold out, the higher the score.

| first ping | score |
|---|---|
| 08:00 | 0 |
| 09:00 | 12 |
| 10:00 | 24 |
| 12:00 | 48 |
| never | 60 (perfect) |

One point per 5 minutes survived. Maximum 60.

Files: `server.py`, `score.py` (CLI), `ping.sh` (phone), `morningscore.service`.

---

## Server

```bash
sudo useradd --system --no-create-home morningscore
sudo mkdir -p /opt/morningscore /var/lib/morningscore
sudo cp server.py /opt/morningscore/
sudo python3 -m venv /opt/morningscore/venv
sudo /opt/morningscore/venv/bin/pip install flask waitress
sudo chown -R morningscore:morningscore /opt/morningscore /var/lib/morningscore

printf 'SCORE_TOKEN=%s\n' "$(openssl rand -hex 24)" | sudo tee /etc/morningscore.env
sudo chmod 600 /etc/morningscore.env

sudo cp morningscore.service /etc/systemd/system/
sudo systemctl enable --now morningscore
```

**Edit `SCORE_TZ` in the service file to your timezone.** If you leave it wrong,
08:00 means 08:00 UTC and every score will be off by hours.

Print your token: `sudo cat /etc/morningscore.env`

The server binds to localhost only. Put Caddy in front (`reverse_proxy 127.0.0.1:8080`),
or use Tailscale and skip the public internet entirely.

## Phone

Install Termux and Termux:Boot from F-Droid, then:

```bash
pkg install curl
mkdir -p ~/.termux/boot
cp ping.sh ~/.termux/boot/ping.sh    # edit URL and TOKEN first
chmod +x ~/.termux/boot/ping.sh
```

Termux:Boot runs it after every reboot. Run `termux-wake-lock` once so Android
does not suspend the loop.

The script pings all day and lets the server ignore anything outside the window.
Simpler than teaching the phone what time it is.

### MIUI

Xiaomi will kill Termux in the background, which produces fake perfect scores.
Settings → Apps → Termux → **Autostart on**, **Battery saver: No restrictions**.
Then lock it in the recents view (swipe down on the card, tap the padlock).

Verify after two days: if you turned your phone on at 09:00 and the score says 60,
MIUI ate the pinger.

## Reading your scores

```bash
export SCORE_URL=https://score.example.com
export SCORE_TOKEN=...

./score.py
#   12 / 60   ######
#   phone was turned on
#   phone came on at 09:00

./score.py --history
#   2026-08-25  12  ######                         09:00
#   2026-08-24  24  ############                   10:00
#   2026-08-23  60  ############################## never
#
#   average: 32.0 / 60
```

During the morning the score counts upward live, so checking it at 10:30 with the
phone still off shows 30 and climbing. Which is the point — but note that checking
it on your phone means turning your phone on, which ends the run. Check it on a
laptop.

## Endpoints

| Route | Purpose |
|---|---|
| `/ping` | the phone calls this; outside 08:00–13:00 it is ignored |
| `/today` | today's score, live |
| `/scores?days=30` | history and average |
| `/healthz` | no auth, for uptime monitoring |

## Honest limitation

A missing ping means "no ping arrived", which covers phone off, no signal, dead
battery, MIUI killing Termux, and your server being down. It cannot tell those apart,
and all of them score as a perfect morning.

Days before you first started the server are excluded from the average, so old empty
days do not count as wins. Server downtime during the window still will. If you want
the number to mean something, do not go looking for that loophole.

## Changing the rules

Everything lives in four constants at the top of `server.py`:

```python
WINDOW_START = time(8, 0)
WINDOW_END = time(13, 0)
SLOT_MINUTES = 5
MAX_SCORE = 60      # keep as (window length in minutes) / SLOT_MINUTES
```
