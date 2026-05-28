#!/bin/bash
# ============================================
# Xray VLESS Reality — Установка на VPS
# Запускать от root на VPS в Стокгольме
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}[*] Установка Xray VLESS Reality на VPS${NC}"

# Проверка root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[!] Запускай от root${NC}"
    exit 1
fi

# Установка зависимостей
echo -e "${YELLOW}[*] Установка зависимостей...${NC}"
apt update && apt install -y curl wget unzip jq openssl

# Установка Xray
echo -e "${YELLOW}[*] Установка Xray...${NC}"
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# Генерация ключей x25519
echo -e "${YELLOW}[*] Генерация ключей Reality...${NC}"
KEYS=$(/usr/local/bin/xray x25519)
PRIVATE_KEY=$(echo "$KEYS" | grep "Private" | awk '{print $3}')
PUBLIC_KEY=$(echo "$KEYS" | grep "Public" | awk '{print $3}')

# Генерация UUID
UUID=$(/usr/local/bin/xray uuid)

# Генерация shortId (8 символов hex)
SHORT_ID=$(openssl rand -hex 8)

# Получение IP сервера
SERVER_IP=$(curl -s4 ifconfig.me || curl -s4 icanhazip.com)

# Целевой сайт для маскировки (SNI)
DEST="www.microsoft.com"
DEST_PORT=443

echo -e "${GREEN}[*] Сгенерированные параметры:${NC}"
echo "  UUID:        $UUID"
echo "  Private Key: $PRIVATE_KEY"
echo "  Public Key:  $PUBLIC_KEY"
echo "  Short ID:    $SHORT_ID"
echo "  Server IP:   $SERVER_IP"
echo "  Dest (SNI):  $DEST"

# Создание конфига сервера
echo -e "${YELLOW}[*] Создание конфига /usr/local/etc/xray/config.json${NC}"
cat > /usr/local/etc/xray/config.json << EOF
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "listen": "0.0.0.0",
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${UUID}",
            "flow": "xtls-rprx-vision"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "${DEST}:${DEST_PORT}",
          "xver": 0,
          "serverNames": [
            "${DEST}",
            "www.microsoft.com",
            "microsoft.com"
          ],
          "privateKey": "${PRIVATE_KEY}",
          "shortIds": [
            "${SHORT_ID}",
            ""
          ]
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": [
          "http",
          "tls",
          "quic"
        ]
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "tag": "direct"
    },
    {
      "protocol": "blackhole",
      "tag": "block"
    }
  ]
}
EOF

# Включение и запуск
echo -e "${YELLOW}[*] Запуск Xray...${NC}"
systemctl daemon-reload
systemctl enable xray
systemctl restart xray

# Проверка статуса
sleep 2
if systemctl is-active --quiet xray; then
    echo -e "${GREEN}[✓] Xray запущен успешно!${NC}"
else
    echo -e "${RED}[✗] Ошибка запуска Xray!${NC}"
    journalctl -u xray --no-pager -n 20
    exit 1
fi

# Генерация ссылки для клиента
VLESS_LINK="vless://${UUID}@${SERVER_IP}:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=${DEST}&fp=chrome&pbk=${PUBLIC_KEY}&sid=${SHORT_ID}&type=tcp&headerType=none#VPS-Stockholm"

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN} УСТАНОВКА ЗАВЕРШЕНА!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Параметры для клиента:${NC}"
echo "  Адрес:       ${SERVER_IP}"
echo "  Порт:        443"
echo "  UUID:        ${UUID}"
echo "  Flow:        xtls-rprx-vision"
echo "  Security:    reality"
echo "  SNI:         ${DEST}"
echo "  Public Key:  ${PUBLIC_KEY}"
echo "  Short ID:    ${SHORT_ID}"
echo "  Fingerprint: chrome"
echo ""
echo -e "${YELLOW}VLESS ссылка (для v2rayNG / Nekobox):${NC}"
echo ""
echo "$VLESS_LINK"
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"

# Сохранение параметров в файл
cat > /usr/local/etc/xray/client-params.txt << EOF
SERVER_IP=${SERVER_IP}
UUID=${UUID}
PUBLIC_KEY=${PUBLIC_KEY}
PRIVATE_KEY=${PRIVATE_KEY}
SHORT_ID=${SHORT_ID}
DEST=${DEST}
VLESS_LINK=${VLESS_LINK}
EOF

echo -e "${YELLOW}Параметры сохранены в /usr/local/etc/xray/client-params.txt${NC}"
