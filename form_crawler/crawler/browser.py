"""Playwright-based browser crawler with modal detection and JS interaction."""

import asyncio
import logging
import json
from typing import Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeout,
    Error as PlaywrightError,
)

from ..config.settings import Settings
from ..config.constants import (
    PAGES_TO_CRAWL,
    FORM_SELECTORS,
    FORM_TRIGGERS,
    CMS_SIGNATURES,
    JS_LIBRARIES,
    ANTIBOT_SIGNATURES,
)
from ..proxy.rotation import ProxyRotator, UserAgentRotator

logger = logging.getLogger(__name__)


class PageResult:
    """Result from crawling a single page."""

    def __init__(self):
        self.url: str = ""
        self.status: int = 0
        self.html: str = ""
        self.forms_html: list[dict] = []  # [{html, selector, is_modal, trigger}]
        self.cms: str = ""
        self.libraries: list[str] = []
        self.antibot: list[str] = []
        self.iframes: list[str] = []
        self.title: str = ""
        self.error: str = ""


class BrowserCrawler:
    """Manages Playwright browser for crawling sites and extracting form HTML."""

    def __init__(
        self,
        settings: Settings,
        proxy_rotator: ProxyRotator,
        ua_rotator: UserAgentRotator,
    ):
        self.settings = settings
        self.proxy = proxy_rotator
        self.ua = ua_rotator
        self._playwright = None
        self._browser: Optional[Browser] = None

    async def start(self):
        """Launch browser."""
        self._playwright = await async_playwright().start()
        launch_args = {
            "headless": self.settings.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        }
        browser_launcher = getattr(self._playwright, self.settings.browser_type)
        self._browser = await browser_launcher.launch(**launch_args)
        logger.info(f"Browser launched: {self.settings.browser_type}, headless={self.settings.headless}")

    async def stop(self):
        """Close browser and playwright."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    async def crawl_site(self, base_url: str) -> list[PageResult]:
        """Crawl a site's key pages and extract form data."""
        results = []

        # Create context with random UA and optional proxy
        context = await self._create_context()

        try:
            # First crawl main page to detect CMS, then other pages
            pages_to_visit = self._build_page_list(base_url)

            for page_url in pages_to_visit:
                try:
                    result = await self._crawl_page(context, page_url, base_url)
                    if result and (result.forms_html or result.status == 200):
                        results.append(result)
                except Exception as e:
                    logger.debug(f"Error crawling {page_url}: {e}")
                    continue

                # Rate limit between pages on same site
                await asyncio.sleep(0.5)

        finally:
            await context.close()

        return results

    async def _create_context(self) -> BrowserContext:
        """Create a browser context with proxy and UA."""
        context_opts = {
            "viewport": {
                "width": self.settings.viewport_width,
                "height": self.settings.viewport_height,
            },
            "user_agent": self.ua.get_random(),
            "locale": "ru-RU",
            "timezone_id": "Europe/Moscow",
            "ignore_https_errors": True,
        }

        # Add proxy if available
        if self.proxy.has_proxies:
            proxy_url = await self.proxy.get_proxy()
            if proxy_url:
                context_opts["proxy"] = self.proxy.get_playwright_proxy(proxy_url)

        context = await self._browser.new_context(**context_opts)

        # Anti-detection scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = {runtime: {}};
        """)

        return context

    def _build_page_list(self, base_url: str) -> list[str]:
        """Build list of URLs to visit."""
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        urls = []
        for path in PAGES_TO_CRAWL:
            urls.append(f"{base}{path}")
        return urls[:self.settings.max_pages_per_site]

    async def _crawl_page(self, context: BrowserContext, url: str, base_url: str) -> Optional[PageResult]:
        """Crawl a single page, interact with modals, extract forms."""
        result = PageResult()
        result.url = url

        page = await context.new_page()
        try:
            # Navigate
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.settings.page_load_timeout * 1000,
            )

            if response is None:
                result.error = "no response"
                return None

            result.status = response.status
            if result.status >= 400:
                return None

            # Wait for page to settle
            await page.wait_for_load_state("networkidle", timeout=10000)
            await asyncio.sleep(1)

            # Get page title
            result.title = await page.title()

            # Detect CMS and libraries
            page_content = await page.content()
            result.cms = self._detect_cms(page_content)
            result.libraries = self._detect_libraries(page_content)
            result.antibot = self._detect_antibot(page_content)

            # Find forms already visible on page
            visible_forms = await self._extract_visible_forms(page)
            result.forms_html.extend(visible_forms)

            # Find and click trigger buttons to open modals
            modal_forms = await self._extract_modal_forms(page)
            result.forms_html.extend(modal_forms)

            # Check iframes for forms
            iframe_forms = await self._extract_iframe_forms(page)
            result.iframes = [f.get("iframe_src", "") for f in iframe_forms]
            result.forms_html.extend(iframe_forms)

            result.html = page_content

        except PlaywrightTimeout:
            result.error = "timeout"
            logger.debug(f"Timeout: {url}")
        except PlaywrightError as e:
            result.error = str(e)[:200]
            logger.debug(f"Playwright error on {url}: {e}")
        except Exception as e:
            result.error = str(e)[:200]
            logger.debug(f"Error on {url}: {e}")
        finally:
            await page.close()

        return result

    async def _extract_visible_forms(self, page: Page) -> list[dict]:
        """Extract all visible form elements from page."""
        forms = []

        for selector in FORM_SELECTORS["forms"]:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    is_visible = await el.is_visible()
                    if not is_visible:
                        continue

                    html = await el.evaluate("e => e.outerHTML")
                    # Get CSS selector path
                    css_path = await el.evaluate("""e => {
                        let path = [];
                        while (e && e.nodeType === Node.ELEMENT_NODE) {
                            let selector = e.nodeName.toLowerCase();
                            if (e.id) { selector += '#' + e.id; path.unshift(selector); break; }
                            else {
                                let sibling = e, nth = 1;
                                while (sibling = sibling.previousElementSibling) {
                                    if (sibling.nodeName === e.nodeName) nth++;
                                }
                                if (nth > 1) selector += ':nth-of-type(' + nth + ')';
                            }
                            path.unshift(selector);
                            e = e.parentNode;
                        }
                        return path.join(' > ');
                    }""")

                    forms.append({
                        "html": html[:10000],  # Cap at 10KB
                        "selector": css_path,
                        "is_modal": False,
                        "trigger": "",
                    })
            except Exception:
                continue

        return forms

    async def _extract_modal_forms(self, page: Page) -> list[dict]:
        """Click trigger buttons and extract forms from opened modals."""
        forms = []
        trigger_texts = FORM_TRIGGERS["buttons"]

        # Find potential trigger buttons
        triggers = []
        for selector in FORM_SELECTORS["buttons"]:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    try:
                        is_visible = await el.is_visible()
                        if not is_visible:
                            continue
                        text = (await el.inner_text()).strip().lower()
                        # Check if button text matches known triggers
                        for trigger_text in trigger_texts:
                            if trigger_text.lower() in text:
                                trigger_selector = await el.evaluate("""e => {
                                    let path = [];
                                    while (e && e.nodeType === Node.ELEMENT_NODE) {
                                        let s = e.nodeName.toLowerCase();
                                        if (e.id) { s += '#' + e.id; path.unshift(s); break; }
                                        path.unshift(s);
                                        e = e.parentNode;
                                    }
                                    return path.join(' > ');
                                }""")
                                triggers.append((el, trigger_selector, text))
                                break
                    except Exception:
                        continue
            except Exception:
                continue

        # Click each trigger and look for new forms
        for el, trigger_sel, trigger_text in triggers[:10]:  # Limit to 10 triggers
            try:
                # Click the trigger
                await el.click(timeout=3000)
                await asyncio.sleep(1)

                # Wait for potential modal/popup
                await page.wait_for_timeout(1500)

                # Look for newly visible modals
                for modal_sel in FORM_SELECTORS["modals"]:
                    modal_elements = await page.query_selector_all(modal_sel)
                    for modal in modal_elements:
                        try:
                            is_visible = await modal.is_visible()
                            if not is_visible:
                                continue

                            # Look for forms inside the modal
                            modal_forms = await modal.query_selector_all("form")
                            for form_el in modal_forms:
                                html = await form_el.evaluate("e => e.outerHTML")
                                css_path = await form_el.evaluate("""e => {
                                    let path = [];
                                    while (e && e.nodeType === Node.ELEMENT_NODE) {
                                        let s = e.nodeName.toLowerCase();
                                        if (e.id) { s += '#' + e.id; path.unshift(s); break; }
                                        path.unshift(s);
                                        e = e.parentNode;
                                    }
                                    return path.join(' > ');
                                }""")
                                forms.append({
                                    "html": html[:10000],
                                    "selector": css_path,
                                    "is_modal": True,
                                    "trigger": trigger_sel,
                                })
                        except Exception:
                            continue

                # Try to close modal (press Escape)
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.debug(f"Modal trigger failed for '{trigger_text}': {e}")
                continue

        return forms

    async def _extract_iframe_forms(self, page: Page) -> list[dict]:
        """Check iframes for embedded forms."""
        forms = []

        for selector in FORM_SELECTORS["iframes"]:
            try:
                iframes = await page.query_selector_all(selector)
                for iframe_el in iframes:
                    src = await iframe_el.get_attribute("src")
                    if not src:
                        continue

                    try:
                        frame = await iframe_el.content_frame()
                        if frame:
                            frame_forms = await frame.query_selector_all("form")
                            for form_el in frame_forms:
                                html = await form_el.evaluate("e => e.outerHTML")
                                forms.append({
                                    "html": html[:10000],
                                    "selector": f"iframe[src*='{src[:50]}'] form",
                                    "is_modal": False,
                                    "trigger": "",
                                    "iframe_src": src,
                                })
                    except Exception:
                        # Can't access cross-origin iframe content
                        forms.append({
                            "html": "",
                            "selector": f"iframe[src*='{src[:50]}']",
                            "is_modal": False,
                            "trigger": "",
                            "iframe_src": src,
                        })
            except Exception:
                continue

        return forms

    @staticmethod
    def _detect_cms(html: str) -> str:
        """Detect CMS from page HTML."""
        html_lower = html.lower()
        for cms, signatures in CMS_SIGNATURES.items():
            for sig in signatures:
                if sig.lower() in html_lower:
                    return cms
        return "unknown"

    @staticmethod
    def _detect_libraries(html: str) -> list[str]:
        """Detect JavaScript libraries used."""
        found = []
        for lib, signatures in JS_LIBRARIES.items():
            for sig in signatures:
                if sig in html:
                    found.append(lib)
                    break
        return found

    @staticmethod
    def _detect_antibot(html: str) -> list[str]:
        """Detect anti-bot protection."""
        found = []
        html_lower = html.lower()
        for name, signatures in ANTIBOT_SIGNATURES.items():
            for sig in signatures:
                if sig.lower() in html_lower:
                    found.append(name)
                    break
        return found
