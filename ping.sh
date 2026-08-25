#!/data/data/com.termux/files/usr/bin/bash
# Runs on the phone (Termux). Sends one "I'm alive" ping every 5 minutes.
#
# The server ignores anything outside 08:00-13:00, so this can just run
# all day and not think about it.

URL="https://score.example.com/ping"
TOKEN="paste-your-token-here"

while true; do
    curl --silent --max-time 20 "$URL?token=$TOKEN" > /dev/null
    sleep 300
done
