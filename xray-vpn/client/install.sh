#!/bin/bash
# ============================================
# Xray VLESS Reality + TProxy — Клиент
# Запускать от root на домашнем Debian
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}[*] Установка Xray клиента с TProxy на домашнем Debian${NC}"

# Проверка root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[!] Запускай от root${NC}"
    exit 1
fi

# Запрос параметров
echo ""
echo -e "${YELLOW}Введи параметры от VPS сервера:${NC}"
echo ""

read -p "IP адрес VPS: " SERVER_IP
read -p "UUID: " UUID
read -p "Public Key: " PUBLIC_KEY
read -p "Short ID: " SHORT_ID
read -p "SNI (dest, например www.microsoft.com): " DEST

# Установка зависимостей
echo -e "${YELLOW}[*] Установка зависимостей...${NC}"
apt update && apt install -y curl wget unzip iptables ipset

# Установка Xray
echo -e "${YELLOW}[*] Установка Xray...${NC}"
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# Включение IP forwarding
echo -e "${YELLOW}[*] Включение IP forwarding...${NC}"
cat > /etc/sysctl.d/99-xray-tproxy.conf << EOF
net.ipv4.ip_forward = 1
net.ipv4.conf.all.route_localnet = 1
net.ipv6.conf.all.forwarding = 1
EOF
sysctl --system

# Создание конфига клиента
echo -e "${YELLOW}[*] Создание конфига /usr/local/etc/xray/config.json${NC}"
cat > /usr/local/etc/xray/config.json << EOF
{
  "log": {
    "loglevel": "warning"
  },
  "dns": {
    "servers": [
      {
        "address": "8.8.8.8",
        "domains": [],
        "skipFallback": false
      },
      {
        "address": "1.1.1.1",
        "domains": [],
        "skipFallback": false
      }
    ],
    "queryStrategy": "UseIP"
  },
  "inbounds": [
    {
      "tag": "tproxy-in",
      "port": 12345,
      "protocol": "dokodemo-door",
      "settings": {
        "network": "tcp,udp",
        "followRedirect": true
      },
      "sniffing": {
        "enabled": true,
        "destOverride": [
          "http",
          "tls",
          "quic"
        ],
        "routeOnly": true
      },
      "streamSettings": {
        "sockopt": {
          "tproxy": "tproxy",
          "mark": 255
        }
      }
    },
    {
      "tag": "dns-in",
      "port": 15353,
      "listen": "0.0.0.0",
      "protocol": "dokodemo-door",
      "settings": {
        "address": "8.8.8.8",
        "port": 53,
        "network": "tcp,udp"
      }
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "vless",
      "settings": {
        "vnext": [
          {
            "address": "${SERVER_IP}",
            "port": 443,
            "users": [
              {
                "id": "${UUID}",
                "encryption": "none",
                "flow": "xtls-rprx-vision"
              }
            ]
          }
        ]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "serverName": "${DEST}",
          "fingerprint": "chrome",
          "publicKey": "${PUBLIC_KEY}",
          "shortId": "${SHORT_ID}"
        },
        "sockopt": {
          "mark": 255
        }
      }
    },
    {
      "tag": "direct",
      "protocol": "freedom",
      "settings": {
        "domainStrategy": "UseIP"
      },
      "streamSettings": {
        "sockopt": {
          "mark": 255
        }
      }
    },
    {
      "tag": "block",
      "protocol": "blackhole",
      "settings": {}
    },
    {
      "tag": "dns-out",
      "protocol": "dns",
      "settings": {
        "address": "8.8.8.8",
        "port": 53
      },
      "streamSettings": {
        "sockopt": {
          "mark": 255
        }
      }
    }
  ],
  "routing": {
    "domainStrategy": "AsIs",
    "rules": [
      {
        "type": "field",
        "inboundTag": ["dns-in"],
        "outboundTag": "dns-out"
      },
      {
        "type": "field",
        "ip": ["${SERVER_IP}"],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "ip": [
          "127.0.0.0/8",
          "10.0.0.0/8",
          "172.16.0.0/12",
          "192.168.0.0/16"
        ],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "protocol": ["bittorrent"],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "port": "0-65535",
        "outboundTag": "proxy"
      }
    ]
  }
}
EOF

# Копирование скриптов iptables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/tproxy-iptables.sh" ]; then
    cp "$SCRIPT_DIR/tproxy-iptables.sh" /usr/local/bin/xray-tproxy-up.sh
    cp "$SCRIPT_DIR/tproxy-clean.sh" /usr/local/bin/xray-tproxy-down.sh
    chmod +x /usr/local/bin/xray-tproxy-up.sh
    chmod +x /usr/local/bin/xray-tproxy-down.sh
fi

# Создание systemd unit с pre/post скриптами
cat > /etc/systemd/system/xray-tproxy.service << EOF
[Unit]
Description=Xray TProxy Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStartPre=/usr/local/bin/xray-tproxy-up.sh
ExecStart=/usr/local/bin/xray run -config /usr/local/etc/xray/config.json
ExecStopPost=/usr/local/bin/xray-tproxy-down.sh
Restart=on-failure
RestartSec=5
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF

# Сохранение параметров
cat > /usr/local/etc/xray/params.env << EOF
SERVER_IP=${SERVER_IP}
UUID=${UUID}
PUBLIC_KEY=${PUBLIC_KEY}
SHORT_ID=${SHORT_ID}
DEST=${DEST}
EOF

echo -e "${GREEN}[✓] Установка завершена!${NC}"
echo ""
echo -e "${YELLOW}Следующие шаги:${NC}"
echo "  1. Проверь конфиг: cat /usr/local/etc/xray/config.json"
echo "  2. Запусти TProxy:  systemctl start xray-tproxy"
echo "  3. Включи автозапуск: systemctl enable xray-tproxy"
echo ""
echo -e "${YELLOW}Для устройств в LAN:${NC}"
echo "  - Укажи этот сервер как default gateway"
echo "  - DNS: адрес этого сервера, порт 15353 (или настрой dnsmasq)"
echo ""
