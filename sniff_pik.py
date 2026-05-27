#!/usr/bin/env python3
"""
sniff_pik.py
Открывает pik.ru/callback в видимом браузере, заполняет форму,
перехватывает реальный POST endpoint и тело запроса.
"""
import asyncio
from playwright.async_api import async_playwright

async def sniff():
    intercepted = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        def on_req(req):
            if req.method == "POST":
                intercepted.append({
                    "url":  req.url,
                    "data": req.post_data,
                })
        page.on("request", on_req)

        print("Открываем pik.ru/callback...")
        await page.goto("https://pik.ru/callback", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # заполняем телефон
        phone_filled = False
        for sel in [
            "input[type='tel']",
            "input[name*='phone']",
            "input[placeholder*='телефон']",
            "input[placeholder*='Телефон']",
            "input[placeholder*='номер']",
        ]:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    await el.fill("+79999999999")
                    phone_filled = True
                    print("Телефон вставлен в:", sel)
                    break
            except Exception:
                continue

        if not phone_filled:
            print("ПОЛЕ ТЕЛЕФОНА НЕ НАЙДЕНО — смотри браузер вручную")

        # заполняем имя
        for sel in [
            "input[name*='name']",
            "input[placeholder*='Имя']",
            "input[placeholder*='имя']",
            "input[placeholder*='ФИО']",
        ]:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    await el.fill("Тест")
                    print("Имя вставлено в:", sel)
                    break
            except Exception:
                continue

        # сбрасываем перехваченные до submit
        intercepted.clear()

        # нажимаем submit
        submitted = False
        for sel in [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Отправить')",
            "button:has-text('Перезвонить')",
            "button:has-text('Заказать звонок')",
            "button:has-text('Заказать')",
        ]:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    submitted = True
                    print("Submit нажат:", sel)
                    break
            except Exception:
                continue

        if not submitted:
            print("КНОПКА SUBMIT НЕ НАЙДЕНА — нажми вручную в браузере")

        await page.wait_for_timeout(5000)

        # фильтруем аналитику
        NOISE = {
            "mc.yandex.ru", "yandex.ru", "google.com",
            "googletagmanager.com", "doubleclick.net",
            "facebook.com", "vk.com",
        }

        clean = [
            r for r in intercepted
            if not any(n in r["url"] for n in NOISE)
        ]

        print()
        print("=" * 60)
        print("ПЕРЕХВАЧЕННЫЕ POST (без аналитики):", len(clean))
        print("=" * 60)
        for r in clean:
            print("URL: ", r["url"])
            data = r["data"] or "(нет тела)"
            print("DATA:", data[:300])
            print()

        if not clean:
            print("Чистых POST не найдено.")
            print("Все перехваченные URL:")
            for r in intercepted:
                print(" ", r["url"][:100])

        input("\nEnter чтобы закрыть браузер...")
        await browser.close()


asyncio.run(sniff())
