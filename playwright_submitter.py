#!/usr/bin/env python3
"""
playwright_submitter.py
Открывает страницу в headless браузере, заполняет форму через DOM,
перехватывает реальный XHR/fetch endpoint.
Для JS-форм у которых нет статичного action (ndv.ru, pik.ru и др.)
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

# pip install playwright && playwright install chromium
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("playwright_submitter.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── сайты которые обрабатываем через Playwright ────────────────────────────────
# format: { "hostname": handler_func_name }
PLAYWRIGHT_TARGETS = {
    "pik.ru",
    "ndv.ru",
    "doma97.ru",
    "msk.uzhedoma.ru",
    "vaychulis.com",
    "msk.cityprof.ru",
    "novostroikino.ru",
}


# ── универсальный обработчик ───────────────────────────────────────────────────
async def submit_via_browser(page_url: str, phone: str, name_val: str) -> dict:
    result = {
        "page_url":       page_url,
        "status":         None,
        "intercepted_url": None,
        "http_code":      None,
        "error":          None,
        "method":         None,
    }

    intercepted = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx     = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ru-RU",
        )
        page = await ctx.new_page()

        # перехватываем все POST-запросы во время сессии
        async def on_request(req):
            if req.method == "POST":
                intercepted.append({
                    "url":     req.url,
                    "method":  req.method,
                    "headers": dict(req.headers),
                })

        page.on("request", on_request)

        try:
            log.info("Открываем %s", page_url)
            await page.goto(page_url, wait_until="networkidle", timeout=30000)

            # ── заполняем телефон ──────────────────────────────────────────────
            phone_filled = False
            for selector in [
                "input[type='tel']",
                "input[name*='phone']",
                "input[name*='Phone']",
                "input[placeholder*='телефон']",
                "input[placeholder*='Телефон']",
                "input[placeholder*='номер']",
                "input[placeholder*='Номер']",
                "input[id*='phone']",
            ]:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=2000):
                        await el.click()
                        await el.fill("")
                        await el.type(phone, delay=50)
                        phone_filled = True
                        log.info("  Телефон вставлен в %s", selector)
                        break
                except Exception:
                    continue

            if not phone_filled:
                # попробуем открыть модалку — кнопки "Перезвонить", "Заявка" и т.п.
                for btn_text in ["Перезвонить", "Заказать звонок", "Callback",
                                 "Оставить заявку", "Связаться", "Узнать цену",
                                 "Получить консультацию"]:
                    try:
                        btn = page.get_by_text(btn_text, exact=False).first
                        if await btn.is_visible(timeout=1500):
                            await btn.click()
                            await page.wait_for_timeout(1500)
                            # пробуем ещё раз
                            for sel in ["input[type='tel']", "input[name*='phone']"]:
                                try:
                                    el = page.locator(sel).first
                                    if await el.is_visible(timeout=2000):
                                        await el.fill("")
                                        await el.type(phone, delay=50)
                                        phone_filled = True
                                        log.info("  Телефон вставлен после клика '%s'", btn_text)
                                        break
                                except Exception:
                                    continue
                            if phone_filled:
                                break
                    except Exception:
                        continue

            # ── заполняем имя ──────────────────────────────────────────────────
            for selector in [
                "input[name*='name']",
                "input[name*='Name']",
                "input[placeholder*='имя']",
                "input[placeholder*='Имя']",
                "input[placeholder*='ФИО']",
                "input[id*='name']",
            ]:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=1500):
                        await el.fill(name_val)
                        break
                except Exception:
                    continue

            if not phone_filled:
                result["status"] = "NO_PHONE_FIELD"
                result["error"]  = "Не нашли поле телефона"
                log.warning("  Не нашли поле телефона на %s", page_url)
                await browser.close()
                return result

            # сбрасываем перехваченные до submit — нам нужны только POST после нажатия
            intercepted.clear()

            # ── нажимаем submit ────────────────────────────────────────────────
            submitted = False
            for selector in [
                "button[type='submit']",
                "input[type='submit']",
                "button.t-submit",
                "button:has-text('Отправить')",
                "button:has-text('Перезвонить')",
                "button:has-text('Заказать')",
                "button:has-text('Отправить')",
                "button:has-text('Получить')",
                "button:has-text('Узнать')",
            ]:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=1500):
                        await btn.click()
                        submitted = True
                        log.info("  Submit нажат: %s", selector)
                        break
                except Exception:
                    continue

            if not submitted:
                result["status"] = "NO_SUBMIT"
                result["error"]  = "Не нашли кнопку отправки"
                await browser.close()
                return result

            # ждём сетевой активности после submit
            await page.wait_for_timeout(3000)

            # ── анализируем перехваченные запросы ─────────────────────────────
            # домены аналитики и трекинга — игнорируем
            NOISE_DOMAINS = {
                "mc.yandex.ru", "yandex.ru", "google.com", "google-analytics.com",
                "googletagmanager.com", "doubleclick.net", "facebook.com",
                "vk.com", "top-fwz1.mail.ru", "counter.yadro.ru",
                "pixel.facebook.com", "analytics", "metrika",
            }

            def is_noise(url: str) -> bool:
                host = urlparse(url).netloc.lower()
                return any(nd in host for nd in NOISE_DOMAINS)

            page_host = urlparse(page_url).netloc
            api_calls = [
                r for r in intercepted
                if not is_noise(r["url"])
                and r["url"].rstrip("/") != page_url.rstrip("/")
            ]

            # логируем все чистые POST для отладки
            if api_calls:
                log.info("  Чистых POST перехвачено: %s", len(api_calls))
                for r in api_calls:
                    log.info("    → %s", r["url"][:120])

            if api_calls:
                best = api_calls[0]  # первый POST после submit — это форма
                result["intercepted_url"] = best["url"]
                result["method"]          = best["method"]
                result["status"]          = "INTERCEPTED"
                result["all_endpoints"]   = [r["url"] for r in api_calls]
                log.info("  Лучший endpoint: %s", best["url"][:120])
            else:
                result["status"] = "NO_XHR"
                result["error"]  = "Нет POST-запросов после submit (кроме аналитики)"
                log.warning("  Нет XHR после submit на %s", page_url)

        except PWTimeout as e:
            result["status"] = "TIMEOUT"
            result["error"]  = str(e)
            log.warning("  Таймаут: %s", page_url)
        except Exception as e:
            result["status"] = "ERROR"
            result["error"]  = str(e)
            log.error("  Ошибка: %s — %s", page_url, e)

        await browser.close()

    return result


# ── список страниц для обхода ──────────────────────────────────────────────────
# уникальные page_url из фейковых форм (endpoint пустой)
FAKE_PAGES = [
    # pik.ru
    "https://pik.ru/callback",
    # ndv.ru
    "https://ndv.ru/uslugi",
    "https://ndv.ru/services",
    # doma97.ru
    "https://doma97.ru/contacts",
    # msk.uzhedoma.ru
    "https://msk.uzhedoma.ru/contacts",
    "https://msk.uzhedoma.ru/",
]


def prompt_config() -> dict:
    SEP = "=" * 55
    print(SEP)
    print("   PLAYWRIGHT SUBMITTER — поиск XHR endpoint'ов")
    print(SEP)

    while True:
        phone = input("\nНомер телефона (напр. +79991234567): ").strip()
        if phone:
            break

    name_input = input("Имя [Тест]: ").strip()
    name_val   = name_input if name_input else "Тест"

    print("\nСайты для обхода:")
    for i, url in enumerate(FAKE_PAGES, 1):
        print(f"  {i}. {url}")

    custom = input("\nДобавить свои URL через запятую (или Enter): ").strip()
    extra  = [u.strip() for u in custom.split(",") if u.strip().startswith("http")]

    pages = FAKE_PAGES + extra

    print()
    print(SEP)
    print(f"  Телефон: {phone}")
    print(f"  Имя:     {name_val}")
    print(f"  Страниц: {len(pages)}")
    print(SEP)

    confirm = input("\nЗапустить? (да/нет) [да]: ").strip().lower()
    if confirm in ("нет", "n", "no", "н"):
        print("Отмена.")
        sys.exit(0)

    return {"phone": phone, "name_val": name_val, "pages": pages}


async def main(phone: str, name_val: str, pages: list):
    import time
    start = time.time()

    results = []
    for url in pages:
        r = await submit_via_browser(url, phone, name_val)
        results.append(r)
        await asyncio.sleep(2)

    elapsed = time.time() - start

    intercepted = [r for r in results if r["status"] == "INTERCEPTED"]
    no_field    = [r for r in results if r["status"] == "NO_PHONE_FIELD"]
    no_xhr      = [r for r in results if r["status"] == "NO_XHR"]
    errors      = [r for r in results if r["status"] in ("ERROR", "TIMEOUT", "NO_SUBMIT")]

    SEP = "=" * 55
    print()
    print(SEP)
    print("  ИТОГИ")
    print(SEP)
    print(f"  Страниц обработано:  {len(results)}")
    print(f"  Время:               {elapsed:.1f} сек")
    print()
    print(f"  ✓ Endpoint найден:   {len(intercepted)}")
    print(f"  — Нет XHR:           {len(no_xhr)}")
    print(f"  — Нет поля телефона: {len(no_field)}")
    print(f"  ✗ Ошибки:            {len(errors)}")

    if intercepted:
        print()
        print("  Найденные endpoints:")
        for r in intercepted:
            print(f"    {r['page_url'][:40]:40} → {r['intercepted_url']}")

    print(SEP)

    out = Path("playwright_results.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Результаты → {out}")
    print()


if __name__ == "__main__":
    cfg = prompt_config()
    asyncio.run(main(**cfg))
