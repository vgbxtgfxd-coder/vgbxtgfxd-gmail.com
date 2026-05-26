"""Search engine abstraction for discovering company websites."""

import asyncio
import logging
import re
from urllib.parse import urlparse, quote_plus
from typing import AsyncGenerator

import aiohttp

from ..config.constants import CATEGORIES, SEARCH_TEMPLATES
from ..config.settings import Settings
from ..proxy.rotation import ProxyRotator, UserAgentRotator

logger = logging.getLogger(__name__)

# Domains to exclude from results
EXCLUDED_DOMAINS = {
    "youtube.com", "vk.com", "ok.ru", "facebook.com", "instagram.com",
    "twitter.com", "t.me", "telegram.org", "whatsapp.com",
    "wikipedia.org", "avito.ru", "yandex.ru", "google.com",
    "mail.ru", "rambler.ru", "bing.com", "duckduckgo.com",
    "2gis.ru", "zoon.ru", "yell.ru", "flamp.ru",
    "drive2.ru", "pikabu.ru", "habr.com",
}


class SearchEngine:
    """Builds search queries and extracts domains from results.
    
    Supports multiple backends:
    - DuckDuckGo HTML (no API key needed)
    - Custom search endpoint (configurable)
    """

    def __init__(
        self,
        settings: Settings,
        proxy_rotator: ProxyRotator,
        ua_rotator: UserAgentRotator,
    ):
        self.settings = settings
        self.proxy = proxy_rotator
        self.ua = ua_rotator
        self._session: aiohttp.ClientSession | None = None
        self._rate_limiter = asyncio.Semaphore(1)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.settings.request_timeout),
                headers={"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5"},
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def generate_queries(
        self, categories: list[str] | None = None, city: str = ""
    ) -> list[str]:
        """Generate all search queries from categories × templates."""
        cats = categories or CATEGORIES
        queries = []
        for cat in cats:
            for template in SEARCH_TEMPLATES:
                q = template.format(category=cat)
                if city:
                    q = f"{q} {city}"
                queries.append(q)
        return queries

    async def search(
        self,
        query: str,
        max_results: int = 20,
    ) -> list[dict]:
        """Execute a search query and return list of {url, title, domain}."""
        async with self._rate_limiter:
            results = await self._search_duckduckgo(query, max_results)
            await asyncio.sleep(self.settings.search_delay)
            return results

    async def search_all(
        self,
        categories: list[str] | None = None,
        city: str = "",
        max_results_per_query: int = 20,
    ) -> AsyncGenerator[dict, None]:
        """Search all queries and yield unique domains."""
        queries = self.generate_queries(categories, city)
        seen_domains = set()

        for i, query in enumerate(queries):
            logger.info(f"Search [{i+1}/{len(queries)}]: {query}")
            try:
                results = await self.search(query, max_results_per_query)
                for r in results:
                    domain = r["domain"]
                    if domain not in seen_domains and domain not in EXCLUDED_DOMAINS:
                        seen_domains.add(domain)
                        yield r
            except Exception as e:
                logger.error(f"Search error for '{query}': {e}")
                continue

    async def _search_duckduckgo(self, query: str, max_results: int) -> list[dict]:
        """Search via DuckDuckGo HTML page (no API key needed)."""
        session = await self._get_session()
        encoded = quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}&kl=ru-ru"

        headers = {
            "User-Agent": self.ua.get_random(),
            "Accept": "text/html",
            "Referer": "https://duckduckgo.com/",
        }

        proxy = await self.proxy.get_proxy() if self.proxy.has_proxies else None

        try:
            async with session.get(url, headers=headers, proxy=proxy) as resp:
                if resp.status != 200:
                    logger.warning(f"DuckDuckGo returned {resp.status} for: {query}")
                    if proxy:
                        await self.proxy.report_failure(proxy)
                    return []

                if proxy:
                    await self.proxy.report_success(proxy)

                html = await resp.text()
                return self._parse_ddg_results(html, max_results)
        except Exception as e:
            logger.error(f"DuckDuckGo request failed: {e}")
            if proxy:
                await self.proxy.report_failure(proxy)
            return []

    def _parse_ddg_results(self, html: str, max_results: int) -> list[dict]:
        """Parse DuckDuckGo HTML results page."""
        from selectolax.parser import HTMLParser

        results = []
        tree = HTMLParser(html)

        # DuckDuckGo HTML results are in .result__a links
        for node in tree.css(".result__a"):
            href = node.attributes.get("href", "")
            title = node.text(strip=True)

            # DDG wraps URLs - extract actual URL
            actual_url = self._extract_url_from_ddg(href)
            if not actual_url:
                continue

            parsed = urlparse(actual_url)
            domain = parsed.netloc.lower().lstrip("www.")

            if domain and domain not in EXCLUDED_DOMAINS:
                results.append({
                    "url": actual_url,
                    "title": title,
                    "domain": domain,
                })

            if len(results) >= max_results:
                break

        return results

    @staticmethod
    def _extract_url_from_ddg(href: str) -> str:
        """Extract actual URL from DuckDuckGo redirect wrapper."""
        if href.startswith("//duckduckgo.com/l/?uddg="):
            from urllib.parse import unquote
            # Extract the uddg parameter
            match = re.search(r"uddg=([^&]+)", href)
            if match:
                return unquote(match.group(1))
        elif href.startswith("http"):
            return href
        return ""

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract clean domain from URL."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
