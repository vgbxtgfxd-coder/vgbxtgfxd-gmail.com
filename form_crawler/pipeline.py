"""Async pipeline orchestrator - main crawl workflow."""

import asyncio
import json
import logging
from typing import Optional

from .config.settings import Settings
from .config.constants import CATEGORIES
from .storage.database import Database
from .storage.models import Company, FormData
from .proxy.rotation import ProxyRotator, UserAgentRotator
from .search.engine import SearchEngine
from .crawler.browser import BrowserCrawler
from .extractor.form_extractor import FormExtractor
from .export.exporter import Exporter

logger = logging.getLogger(__name__)



class Pipeline:
    """Orchestrates the full crawl pipeline:
    1. Search for companies
    2. Crawl their pages
    3. Extract form data
    4. Store results
    5. Export
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.db: Optional[Database] = None
        self.proxy = ProxyRotator(settings.proxy_file)
        self.ua = UserAgentRotator()
        self.search = SearchEngine(settings, self.proxy, self.ua)
        self.extractor = FormExtractor()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._stats = {
            "companies_found": 0,
            "companies_crawled": 0,
            "forms_found": 0,
            "errors": 0,
        }

    async def run(
        self,
        categories: list[str] | None = None,
        city: str = "",
        skip_search: bool = False,
        export_format: str = "all",
    ):
        """Run the full pipeline."""
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent_tasks)

        async with Database(self.settings.db_path) as db:
            self.db = db

            # Phase 1: Search for companies (unless skipped)
            if not skip_search:
                await self._phase_search(categories, city)

            # Phase 2: Crawl and extract
            await self._phase_crawl()

            # Phase 3: Export
            await self._phase_export(export_format)

        await self.search.close()
        self._print_stats()


    async def _phase_search(self, categories: list[str] | None, city: str):
        """Phase 1: Search for companies and store them."""
        logger.info("=" * 60)
        logger.info("PHASE 1: Searching for companies")
        logger.info("=" * 60)

        cats = categories or CATEGORIES
        logger.info(f"Categories: {cats}")
        logger.info(f"City filter: {city or 'none'}")

        count = 0
        async for result in self.search.search_all(cats, city):
            company = Company(
                name=result.get("title", ""),
                site=f"https://{result['domain']}",
                category=self._guess_category(result.get("title", ""), cats),
                city=city,
                status="pending",
            )
            await self.db.insert_company(company)
            count += 1

            if count % 10 == 0:
                logger.info(f"  Found {count} companies so far...")

        self._stats["companies_found"] = count
        logger.info(f"Search complete: {count} companies found")

    async def _phase_crawl(self):
        """Phase 2: Crawl pending companies and extract forms."""
        logger.info("=" * 60)
        logger.info("PHASE 2: Crawling sites and extracting forms")
        logger.info("=" * 60)

        pending = await self.db.get_pending_companies(limit=500)
        logger.info(f"Companies to crawl: {len(pending)}")

        if not pending:
            logger.info("No pending companies to crawl")
            return

        # Process in batches
        batch_size = self.settings.max_concurrent_tasks
        for i in range(0, len(pending), batch_size):
            batch = pending[i:i + batch_size]
            tasks = [self._crawl_company(c) for c in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(
                f"  Progress: {min(i + batch_size, len(pending))}/{len(pending)} "
                f"| Forms found: {self._stats['forms_found']}"
            )


    async def _crawl_company(self, company: Company):
        """Crawl a single company's site."""
        async with self._semaphore:
            logger.debug(f"Crawling: {company.site}")

            try:
                async with BrowserCrawler(self.settings, self.proxy, self.ua) as crawler:
                    page_results = await crawler.crawl_site(company.site)

                # Detect CMS and update company
                cms = ""
                libraries = []
                antibot = []
                for pr in page_results:
                    if pr.cms and pr.cms != "unknown":
                        cms = pr.cms
                    libraries.extend(pr.libraries)
                    antibot.extend(pr.antibot)

                await self.db.update_company(
                    company.id,
                    status="crawled",
                    cms=cms,
                    libraries=json.dumps(list(set(libraries)), ensure_ascii=False),
                    antibot=",".join(set(antibot)),
                )

                # Skip companies with anti-bot protection
                if antibot:
                    logger.info(f"  ⊘ {company.site} - skipped (antibot: {','.join(set(antibot))})")
                    await self.db.update_company(company.id, status="skipped_antibot")
                    self._stats["companies_crawled"] += 1
                    return

                # Extract forms from all page results (callback only, no captcha)
                forms_count = 0
                for page_result in page_results:
                    forms = self.extractor.extract_forms(page_result, company.id)
                    for form_data in forms:
                        # Only save callback-type forms without captcha
                        if form_data.form_type in ("callback", "popup_callback") and form_data.captcha == "none":
                            await self.db.insert_form(form_data)
                            forms_count += 1

                self._stats["companies_crawled"] += 1
                self._stats["forms_found"] += forms_count

                if forms_count > 0:
                    logger.info(f"  ✓ {company.site} - {forms_count} forms found")
                else:
                    logger.debug(f"  - {company.site} - no forms")

            except Exception as e:
                self._stats["errors"] += 1
                await self.db.update_company(company.id, status="error")
                logger.error(f"  ✗ {company.site} - {e}")


    async def _phase_export(self, export_format: str):
        """Phase 3: Export results."""
        logger.info("=" * 60)
        logger.info("PHASE 3: Exporting results")
        logger.info("=" * 60)

        exporter = Exporter(self.db, self.settings.export_dir)

        if export_format == "all":
            paths = await exporter.export_all()
            for fmt, path in paths.items():
                logger.info(f"  Exported {fmt}: {path}")
        elif export_format == "csv":
            path = await exporter.export_csv()
            logger.info(f"  Exported CSV: {path}")
        elif export_format == "xlsx":
            path = await exporter.export_xlsx()
            logger.info(f"  Exported XLSX: {path}")
        elif export_format == "json":
            path = await exporter.export_json()
            logger.info(f"  Exported JSON: {path}")

    def _guess_category(self, title: str, categories: list[str]) -> str:
        """Try to match a search result title to a category."""
        title_lower = title.lower()
        for cat in categories:
            if cat.lower() in title_lower:
                return cat
        return categories[0] if categories else ""

    def _print_stats(self):
        """Print final statistics."""
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)
        logger.info(f"  Companies found:   {self._stats['companies_found']}")
        logger.info(f"  Companies crawled: {self._stats['companies_crawled']}")
        logger.info(f"  Forms extracted:   {self._stats['forms_found']}")
        logger.info(f"  Errors:            {self._stats['errors']}")


async def run_pipeline(
    categories: list[str] | None = None,
    city: str = "",
    skip_search: bool = False,
    export_format: str = "all",
    settings: Settings | None = None,
):
    """Convenience function to run the pipeline."""
    settings = settings or Settings.from_env()
    pipeline = Pipeline(settings)
    await pipeline.run(
        categories=categories,
        city=city,
        skip_search=skip_search,
        export_format=export_format,
    )
