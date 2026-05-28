#!/bin/bash
# Daily cleanup script - runs at 05:00 MSK via cron
# Kills bots, cleans Frigate, restarts services

# 1. Kill bot processes (use exact match to avoid killing this script)
PID_VS=$(pgrep -f "python3 /opt/frigate-bot/video_sender.py" | head -1)
PID_BOT=$(pgrep -f "python3 /opt/frigate-bot/bot.py" | head -1)
[ -n "$PID_VS" ] && kill -9 $PID_VS 2>/dev/null
[ -n "$PID_BOT" ] && kill -9 $PID_BOT 2>/dev/null
sleep 3

# 2. Clean Frigate storage
find /opt/frigate/storage/ -type f -delete 2>/dev/null
echo '' > /opt/frigate-bot/sent_events.txt

# 3. Clean Frigate cache and DB inside container
docker exec frigate rm -rf /tmp/cache/* 2>/dev/null
docker exec frigate rm -f /config/frigate.db /config/frigate.db-shm /config/frigate.db-wal 2>/dev/null

# 4. Restart Frigate
docker restart frigate
sleep 20

# 5. Restart zapret (in case Docker messed up nftables)
/opt/zapret-discord-youtube-linux/service.sh service restart 2>/dev/null
sleep 10

# 6. Start bots
rm -f /tmp/bot.log /tmp/vs.log
nohup /usr/bin/python3 /opt/frigate-bot/bot.py > /tmp/bot.log 2>&1 &
nohup /usr/bin/python3 /opt/frigate-bot/video_sender.py > /tmp/vs.log 2>&1 &

echo "$(date) - Cleanup complete" >> /tmp/cleanup.log
