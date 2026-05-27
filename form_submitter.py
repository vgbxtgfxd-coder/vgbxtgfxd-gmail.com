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
def build_payload(form: Form, phone: str) -> dict:
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
            payload[name] = "Тест"

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
) -> dict:
    url     = get_target_endpoint(form)
    payload = build_payload(form, phone)

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
            submit_form(session, form, phone, semaphore)
            for form in targets
        ]
        results = await asyncio.gather(*tasks)

    ok      = sum(1 for r in results if r["status"] == "OK")
    err     = sum(1 for r in results if r["status"] not in ("OK", "SKIP_NO_URL"))
    skipped = sum(1 for r in results if r["status"] == "SKIP_NO_URL")

    log.info("=" * 50)
    log.info("Готово. OK=%s  ERR=%s  SKIP=%s", ok, err, skipped)
    log.info("=" * 50)

    out_path = Path("submit_results.json")
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Результаты → %s", out_path)


# ── точка входа ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Form load tester")
    parser.add_argument(
        "csv",
        nargs="?",
        default="data/export/forms_export_20260527_110336_forms.csv",
        help="Путь к CSV с формами",
    )
    parser.add_argument(
        "--phone",
        default=PHONE_NUMBER,
        help="Номер телефона для вставки (default: +79991234567)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=CONCURRENCY,
        help="Одновременных запросов",
    )
    parser.add_argument(
        "--no-skip-captcha",
        action="store_true",
        help="Не пропускать формы с капчей",
    )
    args = parser.parse_args()

    CONCURRENCY  = args.concurrency
    SKIP_CAPTCHA = not args.no_skip_captcha

    asyncio.run(main(args.csv, args.phone))
