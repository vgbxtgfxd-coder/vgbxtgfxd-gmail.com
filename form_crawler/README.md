# Form Crawler

Production-ready парсер для поиска сайтов компаний и извлечения структуры форм обратной связи / заказа звонка.

## Возможности

- Поиск компаний по 12 бизнес-категориям через DuckDuckGo
- Обход сайтов с помощью Playwright (headless Chrome)
- Обнаружение форм: видимых, в модалках, в iframe, div-based
- Клик по кнопкам "Заказать звонок" / "Обратный звонок" для открытия модалок
- Извлечение полной структуры форм (поля, action, method, AJAX endpoints)
- Определение CMS (Bitrix, WordPress, Tilda, etc.)
- Определение CAPTCHA (reCAPTCHA v2/v3, hCaptcha)
- Определение anti-bot защиты (Cloudflare, DDoS-Guard, etc.)
- Ротация прокси и User-Agent
- Экспорт в CSV, XLSX, JSON
- Асинхронный пайплайн с rate limiting

## Структура проекта

```
form_crawler/
├── config/          # Настройки, константы, категории
├── search/          # Поиск компаний через поисковики
├── crawler/         # Playwright браузер, обход страниц
├── parser/          # HTML парсинг, детекция форм
├── extractor/       # Извлечение метаданных форм
├── storage/         # SQLite БД, модели данных
├── export/          # Экспорт CSV/XLSX/JSON
├── proxy/           # Ротация прокси и UA
├── pipeline.py      # Оркестратор пайплайна
├── __main__.py      # CLI точка входа
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Установка

### Локально

```bash
cd form_crawler
pip install -r requirements.txt
playwright install chromium
```

### Docker

```bash
cd form_crawler
docker compose build
```

## Использование

### Базовый запуск (все категории)

```bash
python -m form_crawler
```

### Конкретные категории

```bash
python -m form_crawler --categories "застройщики" "клиники" "автосалоны"
```

### С фильтром по городу

```bash
python -m form_crawler --city "Москва" --categories "стоматологии"
```

### Только crawl (поиск уже выполнен, компании в БД)

```bash
python -m form_crawler --skip-search
```

### Только экспорт

```bash
python -m form_crawler --export-only --format xlsx
```

### С прокси

```bash
python -m form_crawler --proxy-file ./proxies.txt --concurrent 10
```

### Docker

```bash
docker compose run crawler --categories "мебель" "окна" --city "СПб"
```

## CLI параметры

| Параметр | Описание | Default |
|----------|----------|---------|
| `--categories` | Категории для поиска | все 12 |
| `--city` | Город/регион | - |
| `--skip-search` | Пропустить поиск | false |
| `--export-only` | Только экспорт | false |
| `--format` | csv/xlsx/json/all | all |
| `--concurrent` | Параллельных задач | 5 |
| `--timeout` | Таймаут запроса (сек) | 30 |
| `--rate-limit` | Задержка между запросами | 1.5s |
| `--headless` | Headless режим | true |
| `--browser` | chromium/firefox/webkit | chromium |
| `--proxy-file` | Файл со списком прокси | - |
| `--log-level` | DEBUG/INFO/WARNING/ERROR | INFO |
| `--db` | Путь к SQLite файлу | data/forms.db |

## Формат прокси (proxies.txt)

```
http://user:pass@host:port
socks5://user:pass@host:port
host:port
```

## База данных

SQLite с двумя таблицами:

### companies
- id, name, site, category, city, cms, libraries, antibot, status

### forms
- id, company_id, page_url, form_type, html, action, method
- submit_type, endpoint, fields, hidden_fields, csrf_token
- captcha, selectors, xpath, js_events, iframe_src
- shadow_dom, is_modal, trigger_selector

## Типы форм

| Тип | Описание |
|-----|----------|
| callback | Обратный звонок / заказать звонок |
| request | Оставить заявку |
| consultation | Консультация |
| contact | Связаться / контакты |
| quiz | Квиз / калькулятор |
| popup_callback | Popup форма обратного звонка |
| order | Заказать / оформить |

## Что НЕ делает этот инструмент

- Не отправляет заявки / формы
- Не делает массовые POST запросы
- Не обходит CAPTCHA
- Не рассылает спам
- Не автозаполняет формы

Только обнаружение и анализ структуры.
