#!/usr/bin/env python3
"""
form_submitter.py
Читает спарсенные формы из CSV, находит те где есть phone-поле,
вставляет номер и шлёт POST-запросы для нагрузочного тестирования.
"""

import asyncio
import csv
import json
import logging
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urljoin

import aiohttp

# ── подтверждённые рабочие endpoints (перехвачены через Playwright) ────────────
# формат: список словарей с url, method, content_type и payload_builder
DIRECT_ENDPOINTS = [
    {
        "label":        "ndv.ru — OrderCallForm",
        "url":          "https://www.ndv.ru/backend-api/realty/forms/OrderCallForm",
        "method":       "POST",
        "content_type": "application/x-www-form-urlencoded",
        "referer":      "https://ndv.ru/services",
        "origin":       "https://www.ndv.ru",
        "payload":      lambda phone, name: {"phone": phone, "name": name},
    },
    {
        "label":        "eyenewton.ru — callback (uzhedoma.ru)",
        "url":          "https://eyenewton.ru/callback/request/create",
        "method":       "POST",
        "content_type": "application/x-www-form-urlencoded",
        "referer":      "https://msk.uzhedoma.ru/contacts",
        "origin":       "https://msk.uzhedoma.ru",
        "payload":      lambda phone, name: {"phone": phone, "name": name},
    },
]

# ── настройки ──────────────────────────────────────────────────────────────────
PHONE_NUMBER = "+79991234567"   # номер который вставляем
CONCURRENCY  = 10               # одновременных запросов
DELAY_MIN    = 0.5              # мин задержка между запросами (сек)
DELAY_MAX    = 2.0              # макс задержка
SKIP_CAPTCHA = True             # пропускать формы с капчей
SKIP_METHODS = {"GET"}          # методы которые не трогаем
TIMEOUT      = 15               # таймаут запроса (сек)
USER_AGENT   = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("submitter.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ── датакласс формы ────────────────────────────────────────────────────────────
@dataclass
class Form:
    form_id:       int
    company_id:    int
    page_url:      str
    form_type:     str
    action:        str
    method:        str
    submit_type:   str
    endpoint:      str
    captcha:       str
    fields:        list = field(default_factory=list)
    hidden_fields: list = field(default_factory=list)


# ── парсинг CSV ────────────────────────────────────────────────────────────────
def load_forms(csv_path: str) -> list:
    forms = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                fields_raw        = row.get("fields", "[]") or "[]"
                hidden_fields_raw = row.get("hidden_fields", "[]") or "[]"
                parsed_fields     = json.loads(fields_raw)
                parsed_hidden     = json.loads(hidden_fields_raw)
                forms.append(Form(
                    form_id       = int(row["id"]),
                    company_id    = int(row["company_id"]),
                    page_url      = row["page_url"],
                    form_type     = row["form_type"],
                    action        = row.get("action", ""),
                    method        = (row.get("method") or "POST").upper(),
                    submit_type   = row.get("submit_type", "form"),
                    endpoint      = row.get("endpoint", ""),
                    captcha       = (row.get("captcha") or "none").lower(),
                    fields        = parsed_fields,
                    hidden_fields = parsed_hidden,
                ))
            except Exception as e:
                log.warning("Строка %s — ошибка парсинга: %s", row.get("id", "?"), e)
    return forms


# ── фильтрация ─────────────────────────────────────────────────────────────────
def has_phone_field(form: Form) -> bool:
    all_fields = form.fields + form.hidden_fields
    for f in all_fields:
        if f.get("purpose") == "phone":
            return True
        if f.get("type") == "tel" and f.get("name"):
            return True
    return False


def get_target_endpoint(form: Form) -> Optional[str]:
    ep = form.endpoint or form.action
    if not ep or not ep.startswith("http"):
        if ep and form.page_url:
            ep = urljoin(form.page_url, ep)
        else:
            ep = form.page_url
    return ep if ep.startswith("http") else None


# ── сборка payload ─────────────────────────────────────────────────────────────
def build_payload(form: Form, phone: str, name_val: str = "Тест") -> dict:
    payload = {}

    # hidden fields — берём verbatim
    for f in form.hidden_fields:
        name = f.get("name")
        if name:
            payload[name] = f.get("value", "")

    # проверяем есть ли Tilda phone mask
    tilda_phone_present = any(
        f.get("name") == "tildaspec-phone-part[]"
        for f in form.fields
    )

    seen_radio = set()
    for f in form.fields:
        name    = f.get("name", "")
        purpose = f.get("purpose", "")
        ftype   = f.get("type", "text")

        if not name:
            continue

        if purpose == "phone" or ftype == "tel":
            if name == "tildaspec-phone-part[]":
                payload[name] = _format_phone_masked(phone)
            else:
                payload[name] = phone

        elif purpose == "name":
            payload[name] = name_val

        elif purpose == "email":
            payload[name] = "test@example.com"

        else:
            if ftype == "radio":
                if name not in seen_radio:
                    payload[name] = f.get("value", "")
                    seen_radio.add(name)
            elif ftype == "checkbox":
                payload[name] = f.get("value", "yes")
            elif ftype not in ("submit", "button", "image", "reset"):
                payload.setdefault(name, "")

    # Tilda: скрытый Phone — дублируем полный номер
    if tilda_phone_present and "Phone" in payload:
        payload["Phone"] = phone

    return payload


def _format_phone_masked(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("7") or digits.startswith("8"):
        digits = digits[1:]
    if len(digits) == 10:
        return "(%s) %s-%s-%s" % (
            digits[:3], digits[3:6], digits[6:8], digits[8:]
        )
    return phone


def _origin(url: str) -> str:
    p = urlparse(url)
    return "%s://%s" % (p.scheme, p.netloc)


# ── отправка одной формы ───────────────────────────────────────────────────────
async def submit_form(
    session: aiohttp.ClientSession,
    form: Form,
    phone: str,
    semaphore: asyncio.Semaphore,
    name_val: str = "Тест",
) -> dict:
    url     = get_target_endpoint(form)
    payload = build_payload(form, phone, name_val)

    result = {
        "form_id":      form.form_id,
        "url":          url,
        "page_url":     form.page_url,
        "form_type":    form.form_type,
        "captcha":      form.captcha,
        "status":       None,
        "http_code":    None,
        "error":        None,
        "payload_keys": list(payload.keys()),
    }

    if not url:
        result["status"] = "SKIP_NO_URL"
        log.warning("[%s] нет endpoint — пропускаем", form.form_id)
        return result

    async with semaphore:
        await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        try:
            headers = {
                "User-Agent": USER_AGENT,
                "Referer":    form.page_url,
                "Origin":     _origin(form.page_url),
            }
            if form.submit_type == "ajax":
                headers["X-Requested-With"] = "XMLHttpRequest"

            timeout = aiohttp.ClientTimeout(total=TIMEOUT)

            async with session.post(
                url,
                data=payload,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                ssl=False,
            ) as resp:
                body = await resp.text(errors="replace")
                result["http_code"] = resp.status
                result["status"]    = "OK" if resp.status < 400 else "HTTP_ERR"
                log.info(
                    "[%s] %s → %s  (%s bytes)",
                    form.form_id,
                    form.page_url[:55],
                    resp.status,
                    len(body),
                )

        except asyncio.TimeoutError:
            result["status"] = "TIMEOUT"
            log.warning("[%s] таймаут %s", form.form_id, url[:60])

        except aiohttp.ClientConnectorError as e:
            result["status"] = "CONN_ERR"
            result["error"]  = str(e)
            log.warning("[%s] коннект ошибка: %s", form.form_id, e)

        except Exception as e:
            result["status"] = "ERROR"
            result["error"]  = str(e)
            log.error("[%s] неожиданная ошибка: %s", form.form_id, e)

    return result


async def submit_direct_endpoints(
    session: aiohttp.ClientSession,
    phone: str,
    name_val: str,
    semaphore: asyncio.Semaphore,
) -> list:
    """Отправка на подтверждённые endpoints напрямую без CSV."""
    results = []
    for ep in DIRECT_ENDPOINTS:
        async with semaphore:
            await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            result = {
                "label":    ep["label"],
                "url":      ep["url"],
                "status":   None,
                "http_code": None,
                "error":    None,
                "response": None,
            }
            try:
                payload  = ep["payload"](phone, name_val)
                headers  = {
                    "User-Agent":   USER_AGENT,
                    "Referer":      ep.get("referer", ""),
                    "Origin":       ep.get("origin", ""),
                    "Content-Type": ep.get("content_type", "application/x-www-form-urlencoded"),
                }
                timeout  = aiohttp.ClientTimeout(total=TIMEOUT)
                async with session.post(
                    ep["url"],
                    data=payload if "urlencoded" in ep.get("content_type","") else None,
                    json=payload if "json" in ep.get("content_type","") else None,
                    headers=headers,
                    timeout=timeout,
                    ssl=False,
                ) as resp:
                    body = await resp.text(errors="replace")
                    result["http_code"] = resp.status
                    result["response"]  = body[:300]
                    result["status"]    = "OK" if resp.status < 400 else "HTTP_ERR"
                    log.info("[DIRECT] %s → %s | %s", ep["label"], resp.status, body[:80])
            except Exception as e:
                result["status"] = "ERROR"
                result["error"]  = str(e)
                log.error("[DIRECT] %s ошибка: %s", ep["label"], e)
            results.append(result)
    return results


# ── главный цикл ───────────────────────────────────────────────────────────────
async def main(csv_path: str, phone: str):
    log.info("Загружаем формы из %s", csv_path)
    all_forms = load_forms(csv_path)
    log.info("Всего форм: %s", len(all_forms))

    targets          = []
    skipped_captcha  = 0
    skipped_no_phone = 0
    skipped_method   = 0

    for form in all_forms:
        if form.method in SKIP_METHODS:
            skipped_method += 1
            continue
        if SKIP_CAPTCHA and form.captcha not in ("none", "", "unknown"):
            skipped_captcha += 1
            continue
        if not has_phone_field(form):
            skipped_no_phone += 1
            continue
        targets.append(form)

    log.info(
        "К отправке: %s  (пропущено: капча=%s, нет_телефона=%s, метод=%s)",
        len(targets), skipped_captcha, skipped_no_phone, skipped_method,
    )

    if not targets:
        log.error("Нет форм для отправки. Выход.")
        return

    semaphore = asyncio.Semaphore(CONCURRENCY)
    connector = aiohttp.TCPConnector(ssl=False, limit=CONCURRENCY)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            submit_form(session, form, phone, semaphore, name_val)
            for form in targets
        ]
        results = await asyncio.gather(*tasks)


# ── точка входа ────────────────────────────────────────────────────────────────
def prompt_config() -> dict:
    """Интерактивный мастер настройки перед запуском."""
    SEP = "=" * 55

    print(SEP)
    print("   FORM SUBMITTER — настройка запуска")
    print(SEP)

    # CSV файл
    default_csv = "data/export/forms_export_20260527_110336_forms.csv"
    csv_input = input(f"\nПуть к CSV [{default_csv}]: ").strip()
    csv_path = csv_input if csv_input else default_csv

    # Телефон
    while True:
        phone = input("Номер телефона для вставки (напр. +79991234567): ").strip()
        if phone:
            break
        print("  → номер обязателен")

    # Имя
    name_input = input("Имя для поля 'name' [Тест]: ").strip()
    name_val = name_input if name_input else "Тест"

    # Concurrency
    conc_input = input("Одновременных запросов [10]: ").strip()
    try:
        conc = int(conc_input) if conc_input else 10
        conc = max(1, min(conc, 50))
    except ValueError:
        conc = 10

    # Задержка
    delay_input = input("Задержка между запросами сек (мин-макс, напр. 0.5-2.0) [0.5-2.0]: ").strip()
    delay_min, delay_max = 0.5, 2.0
    if delay_input and "-" in delay_input:
        try:
            parts = delay_input.split("-")
            delay_min = float(parts[0])
            delay_max = float(parts[1])
        except ValueError:
            pass

    # Таймаут
    timeout_input = input("Таймаут запроса сек [15]: ").strip()
    try:
        timeout_val = int(timeout_input) if timeout_input else 15
    except ValueError:
        timeout_val = 15

    # Пропускать капчу
    captcha_input = input("Пропускать формы с капчей? (да/нет) [да]: ").strip().lower()
    skip_cap = captcha_input not in ("нет", "n", "no", "н")

    # Типы форм
    print("\nТипы форм: callback, contact, quiz, all")
    types_input = input("Какие типы отправлять? [all]: ").strip().lower()
    if types_input and types_input != "all":
        form_types = {t.strip() for t in types_input.split(",")}
    else:
        form_types = None  # все

    print()
    print(SEP)
    print("  Конфигурация:")
    print(f"  CSV:          {csv_path}")
    print(f"  Телефон:      {phone}")
    print(f"  Имя:          {name_val}")
    print(f"  Потоки:       {conc}")
    print(f"  Задержка:     {delay_min}-{delay_max} сек")
    print(f"  Таймаут:      {timeout_val} сек")
    print(f"  Пропуск капч: {'да' if skip_cap else 'нет'}")
    print(f"  Типы форм:    {', '.join(form_types) if form_types else 'все'}")
    print(SEP)

    confirm = input("\nЗапустить? (да/нет) [да]: ").strip().lower()
    if confirm in ("нет", "n", "no", "н"):
        print("Отмена.")
        sys.exit(0)

    return {
        "csv_path":   csv_path,
        "phone":      phone,
        "name_val":   name_val,
        "conc":       conc,
        "delay_min":  delay_min,
        "delay_max":  delay_max,
        "timeout":    timeout_val,
        "skip_cap":   skip_cap,
        "form_types": form_types,
    }


async def main(csv_path: str, phone: str, name_val: str = "Тест", form_types: set = None):
    import time
    start_time = time.time()

    log.info("Загружаем формы из %s", csv_path)
    all_forms = load_forms(csv_path)
    log.info("Всего форм: %s", len(all_forms))

    targets          = []
    skipped_captcha  = 0
    skipped_no_phone = 0
    skipped_method   = 0
    skipped_type     = 0

    for form in all_forms:
        if form.method in SKIP_METHODS:
            skipped_method += 1
            continue
        if SKIP_CAPTCHA and form.captcha not in ("none", "", "unknown"):
            skipped_captcha += 1
            continue
        if not has_phone_field(form):
            skipped_no_phone += 1
            continue
        if form_types and form.form_type not in form_types:
            skipped_type += 1
            continue
        targets.append(form)

    log.info(
        "К отправке: %s  (пропущено: капча=%s, нет_телефона=%s, метод=%s, тип=%s)",
        len(targets), skipped_captcha, skipped_no_phone, skipped_method, skipped_type,
    )

    if not targets:
        log.error("Нет форм для отправки. Выход.")
        return

    semaphore = asyncio.Semaphore(CONCURRENCY)
    connector = aiohttp.TCPConnector(ssl=False, limit=CONCURRENCY)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            submit_form(session, form, phone, semaphore)
            for form in targets
        ]
        # добавляем прямые endpoints
        direct_task = submit_direct_endpoints(session, phone, name_val, semaphore)
        csv_results    = await asyncio.gather(*tasks)
        direct_results = await direct_task

    results = list(csv_results) + [
        {**r, "form_id": f"direct_{i}", "page_url": r["url"], "form_type": "direct"}
        for i, r in enumerate(direct_results)
    ]

    elapsed = time.time() - start_time

    # ── финальная статистика ───────────────────────────────────────────────────
    ok       = [r for r in results if r["status"] == "OK"]
    http_err = [r for r in results if r["status"] == "HTTP_ERR"]
    timeouts = [r for r in results if r["status"] == "TIMEOUT"]
    conn_err = [r for r in results if r["status"] == "CONN_ERR"]
    other    = [r for r in results if r["status"] not in ("OK", "HTTP_ERR", "TIMEOUT", "CONN_ERR", "SKIP_NO_URL")]
    skipped  = [r for r in results if r["status"] == "SKIP_NO_URL"]

    SEP = "=" * 55
    print()
    print(SEP)
    print("  ИТОГИ")
    print(SEP)
    print(f"  Всего форм в файле:     {len(all_forms)}")
    print(f"  Отправлено запросов:    {len(results)}")
    print(f"  Время выполнения:       {elapsed:.1f} сек")
    print(f"  Среднее на запрос:      {elapsed/len(results):.2f} сек" if results else "")
    print()
    print(f"  ✓ OK (2xx/3xx):         {len(ok)}")
    print(f"  ✗ HTTP ошибки (4xx/5xx):{len(http_err)}")
    print(f"  ⏱ Таймауты:             {len(timeouts)}")
    print(f"  ✗ Ошибки соединения:    {len(conn_err)}")
    print(f"  ? Прочие ошибки:        {len(other)}")
    print(f"  — Пропущено (нет URL):  {len(skipped)}")
    print()
    print(f"  Пропущено при фильтре:")
    print(f"    капча:                {skipped_captcha}")
    print(f"    нет телефона:         {skipped_no_phone}")
    print(f"    метод GET:            {skipped_method}")
    if skipped_type:
        print(f"    тип формы:          {skipped_type}")

    if http_err:
        print()
        print("  HTTP ошибки по сайтам:")
        from collections import Counter
        from urllib.parse import urlparse
        domains = Counter(urlparse(r["page_url"]).netloc for r in http_err)
        for domain, count in domains.most_common():
            print(f"    {domain}: {count}")

    if direct_results:
        print()
        print("  Прямые endpoints (подтверждённые):")
        for r in direct_results:
            icon = "✓" if r["status"] == "OK" else "✗"
            print(f"    {icon} {r['label'][:45]:45} → {r['http_code']} | {(r.get('response') or '')[:60]}")

    print(SEP)

    out_path = Path("submit_results.json")
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Детальные результаты → {out_path}")
    print()


if __name__ == "__main__":
    cfg = prompt_config()

    CONCURRENCY  = cfg["conc"]
    SKIP_CAPTCHA = cfg["skip_cap"]
    DELAY_MIN    = cfg["delay_min"]
    DELAY_MAX    = cfg["delay_max"]
    TIMEOUT      = cfg["timeout"]

    asyncio.run(main(
        csv_path   = cfg["csv_path"],
        phone      = cfg["phone"],
        name_val   = cfg["name_val"],
        form_types = cfg["form_types"],
    ))
