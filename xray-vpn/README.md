# Xray VLESS Reality + TProxy

## Схема

```
┌─────────────┐         ┌─────────────────────────┐         ┌──────────────────┐
│   Android   │────────►│   VPS Стокгольм         │◄────────│  Домашний Debian │
│  (v2rayNG)  │  VLESS  │   Xray Server           │  VLESS  │  Xray + TProxy   │
│             │ Reality │   (VLESS Reality)        │ Reality │  (шлюз для LAN)  │
└─────────────┘         └─────────────────────────┘         └──────────────────┘
                                                                     │
                                                              ┌──────┴──────┐
                                                              │  LAN devices │
                                                              │  (все ходят  │
                                                              │  через VPS)  │
                                                              └─────────────┘
```

## Компоненты

| Файл | Назначение |
|------|-----------|
| `server/install.sh` | Установка Xray на VPS (Стокгольм) |
| `server/config.json` | Конфиг сервера VLESS Reality |
| `client/install.sh` | Установка Xray на домашний Debian |
| `client/config.json` | Конфиг клиента с TProxy inbound |
| `client/tproxy-iptables.sh` | Правила iptables для TProxy |
| `client/tproxy-clean.sh` | Удаление правил iptables |
| `android/README.md` | Инструкция для v2rayNG на Android |

## Порядок установки

1. **VPS Стокгольм** — запустить `server/install.sh`
2. **Домашний Debian** — запустить `client/install.sh`, затем `client/tproxy-iptables.sh`
3. **Android** — импортировать ссылку из вывода `server/install.sh` в v2rayNG

## Как работает TProxy

TProxy (Transparent Proxy) перехватывает ВЕСЬ трафик устройств в локальной сети
без настройки прокси на каждом устройстве. Домашний Debian работает как шлюз —
устройства в LAN просто указывают его как default gateway и весь их трафик
автоматически идёт через VPS в Стокгольме.
