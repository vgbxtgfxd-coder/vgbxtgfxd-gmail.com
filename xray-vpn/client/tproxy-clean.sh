#!/bin/bash
# ============================================
# TProxy iptables rules — очистка
# Убирает все правила TProxy
# ============================================

set -e

TABLE=100

# Удаление цепочек из основных
iptables -t mangle -D PREROUTING -j XRAY_PREROUTING 2>/dev/null || true
iptables -t mangle -D OUTPUT -j XRAY_OUTPUT 2>/dev/null || true
iptables -t nat -D PREROUTING -j XRAY_DNS 2>/dev/null || true

# Очистка и удаление цепочек
iptables -t mangle -F XRAY_PREROUTING 2>/dev/null || true
iptables -t mangle -X XRAY_PREROUTING 2>/dev/null || true
iptables -t mangle -F XRAY_OUTPUT 2>/dev/null || true
iptables -t mangle -X XRAY_OUTPUT 2>/dev/null || true
iptables -t nat -F XRAY_DNS 2>/dev/null || true
iptables -t nat -X XRAY_DNS 2>/dev/null || true

# Удаление правил маршрутизации
ip rule del fwmark 1 table $TABLE 2>/dev/null || true
ip route del local 0.0.0.0/0 dev lo table $TABLE 2>/dev/null || true

echo "[✓] TProxy iptables rules removed"
