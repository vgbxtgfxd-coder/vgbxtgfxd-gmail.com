# Frigate Server Config

Конфигурация видеонаблюдения Frigate + Telegram бот для сервера Haserv.

## Структура

```
frigate/config.yml    - конфиг Frigate NVR
frigate-bot/bot.py    - Telegram бот (команды, статус, снимки)
frigate-bot/video_sender.py - отправка видео-алертов в ТГ
deploy.sh             - скрипт деплоя на сервер
```

## Деплой на сервер

### Первая настройка

```bash
cd ~
git clone https://github.com/vgbxtgfxd-coder/vgbxtgfxd-gmail.com.git server-config
```

### Применить изменения

```bash
cd ~/server-config
git pull
sudo bash deploy.sh
```

### Автодеплой (cron каждые 5 минут)

```bash
sudo crontab -e
# Добавить:
*/5 * * * * cd /root/server-config && git pull -q && bash deploy.sh >> /tmp/deploy.log 2>&1
```

## Сервер

- **Frigate**: Docker `--network host`, порт 5000
- **Камера**: Dahua, RTSP 192.168.0.113:554
- **Детекция**: CPU (TFLite), person only
- **Бот**: @Camera_253bot
- **Zapret**: обход блокировки Telegram/YouTube/Discord
- **Tailscale**: удалённый доступ

## Ежедневная очистка (05:00 MSK)

Cron удаляет все записи, события, БД и перезапускает Frigate + zapret + бот.

## Параметры детекции

- FPS: 4
- Motion threshold: 30
- Min score: 0.65
- Threshold: 0.75
- Min duration для алерта: 3 сек
- Группировка событий: 30 сек
