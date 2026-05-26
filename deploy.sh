#!/bin/bash
# Deploy script for Frigate config and bot
# Run on server: sudo bash deploy.sh
# Or auto-pull via cron

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
FRIGATE_CONFIG="/opt/frigate/config/config.yml"
BOT_DIR="/opt/frigate-bot"

echo "=== Frigate Deploy ==="
echo "Source: $REPO_DIR"
echo ""

# 1. Update Frigate config
if ! diff -q "$REPO_DIR/frigate/config.yml" "$FRIGATE_CONFIG" >/dev/null 2>&1; then
    echo "[*] Updating Frigate config..."
    cp "$REPO_DIR/frigate/config.yml" "$FRIGATE_CONFIG"
    FRIGATE_CHANGED=1
else
    echo "[=] Frigate config unchanged"
    FRIGATE_CHANGED=0
fi

# 2. Update bot scripts
BOT_CHANGED=0
for f in bot.py video_sender.py; do
    if ! diff -q "$REPO_DIR/frigate-bot/$f" "$BOT_DIR/$f" >/dev/null 2>&1; then
        echo "[*] Updating $f..."
        cp "$REPO_DIR/frigate-bot/$f" "$BOT_DIR/$f"
        BOT_CHANGED=1
    else
        echo "[=] $f unchanged"
    fi
done

# 3. Restart services if changed
if [ "$FRIGATE_CHANGED" -eq 1 ]; then
    echo "[*] Restarting Frigate..."
    docker restart frigate
    sleep 15
    echo "[+] Frigate restarted"
fi

if [ "$BOT_CHANGED" -eq 1 ]; then
    echo "[*] Restarting bot..."
    pkill -9 -f "python3 /opt/frigate-bot/bot.py" 2>/dev/null || true
    pkill -9 -f "python3 /opt/frigate-bot/video_sender.py" 2>/dev/null || true
    sleep 2
    nohup /usr/bin/python3 /opt/frigate-bot/bot.py > /tmp/bot.log 2>&1 &
    nohup /usr/bin/python3 /opt/frigate-bot/video_sender.py > /tmp/vs.log 2>&1 &
    echo "[+] Bot restarted"
fi

echo ""
echo "=== Deploy complete ==="
