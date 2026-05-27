# Настройка Android — v2rayNG

## Установка

1. Скачай **v2rayNG** из Google Play или GitHub:
   https://github.com/2dust/v2rayNG/releases

## Импорт конфига

### Способ 1: VLESS ссылка (самый простой)

После запуска `server/install.sh` на VPS, скрипт выдаст ссылку вида:
```
vless://UUID@IP:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.microsoft.com&fp=chrome&pbk=PUBLIC_KEY&sid=SHORT_ID&type=tcp&headerType=none#VPS-Stockholm
```

В v2rayNG:
1. Нажми `+` → **Импорт из буфера обмена**
2. Вставь ссылку
3. Готово!

### Способ 2: Ручная настройка

1. Нажми `+` → **Добавить [VLESS] сервер вручную**
2. Заполни:

| Поле | Значение |
|------|----------|
| Remarks | VPS Stockholm |
| Address | IP_АДРЕС_VPS |
| Port | 443 |
| UUID | (из вывода install.sh) |
| Flow | xtls-rprx-vision |
| Encryption | none |
| Network | tcp |
| TLS | reality |
| SNI | www.microsoft.com |
| Fingerprint | chrome |
| PublicKey | (из вывода install.sh) |
| ShortId | (из вывода install.sh) |

3. Сохрани и подключись

## Настройки маршрутизации

В v2rayNG → Настройки → Маршрутизация:
- Выбери **Обойти адреса РФ** или **Глобальный прокси** (весь трафик через VPN)

## Проверка

1. Подключись в v2rayNG
2. Открой https://2ip.ru — должен показать IP Стокгольма
3. Открой заблокированный сайт — должен открыться

## Советы

- **Fingerprint = chrome** — имитирует браузер Chrome, лучшая маскировка
- **Reality** не требует сертификатов — DPI не может отличить от обычного HTTPS
- Если не работает — проверь что порт 443 открыт на VPS (обычно открыт по умолчанию)
