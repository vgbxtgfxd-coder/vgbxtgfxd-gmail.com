#!/bin/bash
# ============================================
# TProxy iptables rules — включение
# Перенаправляет весь трафик через Xray
# ============================================

set -e

# Загрузка параметров
if [ -f /usr/local/etc/xray/params.env ]; then
    source /usr/local/etc/xray/params.env
fi

# Порт TProxy в Xray
TPROXY_PORT=12345
# Метка для пакетов, которые НЕ нужно проксировать (от самого Xray)
MARK=255
# Имя таблицы маршрутизации
TABLE=100

# ─── Создание таблицы маршрутизации для TProxy ───
ip rule add fwmark 1 table $TABLE 2>/dev/null || true
ip route add local 0.0.0.0/0 dev lo table $TABLE 2>/dev/null || true

# ─── MANGLE таблица — TProxy для входящего трафика (PREROUTING) ───
iptables -t mangle -N XRAY_PREROUTING 2>/dev/null || iptables -t mangle -F XRAY_PREROUTING

# Не трогаем пакеты с меткой Xray (исходящие от самого xray)
iptables -t mangle -A XRAY_PREROUTING -m mark --mark $MARK -j RETURN

# Не проксируем локальные адреса
iptables -t mangle -A XRAY_PREROUTING -d 127.0.0.0/8 -j RETURN
iptables -t mangle -A XRAY_PREROUTING -d 10.0.0.0/8 -j RETURN
iptables -t mangle -A XRAY_PREROUTING -d 172.16.0.0/12 -j RETURN
iptables -t mangle -A XRAY_PREROUTING -d 192.168.0.0/16 -j RETURN
iptables -t mangle -A XRAY_PREROUTING -d 224.0.0.0/4 -j RETURN
iptables -t mangle -A XRAY_PREROUTING -d 255.255.255.255 -j RETURN

# Не проксируем трафик к VPS (чтобы не зациклить)
if [ -n "$SERVER_IP" ]; then
    iptables -t mangle -A XRAY_PREROUTING -d "$SERVER_IP" -j RETURN
fi

# Всё остальное — TProxy
iptables -t mangle -A XRAY_PREROUTING -p tcp -j TPROXY --on-port $TPROXY_PORT --tproxy-mark 1
iptables -t mangle -A XRAY_PREROUTING -p udp -j TPROXY --on-port $TPROXY_PORT --tproxy-mark 1

# Подключаем цепочку
iptables -t mangle -A PREROUTING -j XRAY_PREROUTING

# ─── MANGLE таблица — для локального трафика самого сервера (OUTPUT) ───
iptables -t mangle -N XRAY_OUTPUT 2>/dev/null || iptables -t mangle -F XRAY_OUTPUT

# Не трогаем пакеты от Xray (с меткой 255)
iptables -t mangle -A XRAY_OUTPUT -m mark --mark $MARK -j RETURN

# Не проксируем локальные адреса
iptables -t mangle -A XRAY_OUTPUT -d 127.0.0.0/8 -j RETURN
iptables -t mangle -A XRAY_OUTPUT -d 10.0.0.0/8 -j RETURN
iptables -t mangle -A XRAY_OUTPUT -d 172.16.0.0/12 -j RETURN
iptables -t mangle -A XRAY_OUTPUT -d 192.168.0.0/16 -j RETURN
iptables -t mangle -A XRAY_OUTPUT -d 224.0.0.0/4 -j RETURN
iptables -t mangle -A XRAY_OUTPUT -d 255.255.255.255 -j RETURN

# Не проксируем трафик к VPS
if [ -n "$SERVER_IP" ]; then
    iptables -t mangle -A XRAY_OUTPUT -d "$SERVER_IP" -j RETURN
fi

# Метим локальный трафик для перенаправления
iptables -t mangle -A XRAY_OUTPUT -p tcp -j MARK --set-mark 1
iptables -t mangle -A XRAY_OUTPUT -p udp -j MARK --set-mark 1

# Подключаем цепочку
iptables -t mangle -A OUTPUT -j XRAY_OUTPUT

# ─── DNS перенаправление (опционально) ───
# Перенаправляем DNS запросы на Xray DNS inbound
iptables -t nat -N XRAY_DNS 2>/dev/null || iptables -t nat -F XRAY_DNS
iptables -t nat -A XRAY_DNS -p udp --dport 53 -j REDIRECT --to-ports 15353
iptables -t nat -A XRAY_DNS -p tcp --dport 53 -j REDIRECT --to-ports 15353
iptables -t nat -A PREROUTING -j XRAY_DNS

echo "[✓] TProxy iptables rules applied"
