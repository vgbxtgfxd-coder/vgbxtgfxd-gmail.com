"""CLI entry point for form_crawler."""

import asyncio
import argparse
import sys

from .config.settings import Settings
from .config.constants import CATEGORIES
from .logging_config import setup_logging
from .pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        prog="form_crawler",
        description="Discover company websites and extract contact/callback form structures.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline - all categories
  python -m form_crawler

  # Specific categories
  python -m form_crawler --categories "застройщики" "клиники" "автосалоны"

  # With city filter
  python -m form_crawler --city "Москва" --categories "стоматологии"

  # Skip search phase, only crawl pending from DB
  python -m form_crawler --skip-search

  # Export only (no search or crawl)
  python -m form_crawler --export-only --format xlsx

  # Custom settings
  python -m form_crawler --concurrent 10 --headless --timeout 60
        """,
    )

    # Main options
    parser.add_argument(
        "--categories", "-c",
        nargs="+",
        default=None,
        help=f"Categories to search. Available: {', '.join(CATEGORIES)}",
    )
    parser.add_argument(
        "--city",
        default="",
        help="City/region filter for search queries",
    )
    parser.add_argument(
        "--skip-search",
        action="store_true",
        help="Skip search phase, only crawl pending companies from DB",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Only export existing data, no search or crawl",
    )

    # Export options
    parser.add_argument(
        "--format", "-f",
        choices=["csv", "xlsx", "json", "all"],
        default="all",
        help="Export format (default: all)",
    )

    # Performance options
    parser.add_argument(
        "--concurrent", "-n",
        type=int,
        default=5,
        help="Max concurrent crawl tasks (default: 5)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.5,
        help="Delay between requests to same domain (default: 1.5s)",
    )

    # Browser options
    parser.add_argument(
        "--headless/--no-headless",
        dest="headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run browser in headless mode (default: true)",
    )
    parser.add_argument(
        "--browser",
        choices=["chromium", "firefox", "webkit"],
        default="chromium",
        help="Browser to use (default: chromium)",
    )

    # Proxy
    parser.add_argument(
        "--proxy-file",
        default=None,
        help="Path to proxy list file",
    )

    # Logging
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output",
    )

    # Database
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite database file",
    )

    args = parser.parse_args()

    # Build settings
    settings = Settings.from_env()
    settings.max_concurrent_tasks = args.concurrent
    settings.request_timeout = args.timeout
    settings.rate_limit_delay = args.rate_limit
    settings.headless = args.headless
    settings.browser_type = args.browser
    settings.log_level = "WARNING" if args.quiet else args.log_level

    if args.proxy_file:
        from pathlib import Path
        settings.proxy_file = Path(args.proxy_file)
    if args.db:
        from pathlib import Path
        settings.db_path = Path(args.db)

    # Setup logging
    setup_logging(settings.log_level, settings.log_dir, log_to_file=True)

    # Handle export-only mode
    if args.export_only:
        asyncio.run(_export_only(settings, args.format))
        return

    # Run full pipeline
    asyncio.run(
        run_pipeline(
            categories=args.categories,
            city=args.city,
            skip_search=args.skip_search,
            export_format=args.format,
            settings=settings,
        )
    )


async def _export_only(settings: Settings, export_format: str):
    """Export existing data without crawling."""
    from .storage.database import Database
    from .export.exporter import Exporter

    async with Database(settings.db_path) as db:
        exporter = Exporter(db, settings.export_dir)
        if export_format == "all":
            paths = await exporter.export_all()
            for fmt, path in paths.items():
                print(f"Exported {fmt}: {path}")
        elif export_format == "csv":
            path = await exporter.export_csv()
            print(f"Exported: {path}")
        elif export_format == "xlsx":
            path = await exporter.export_xlsx()
            print(f"Exported: {path}")
        elif export_format == "json":
            path = await exporter.export_json()
            print(f"Exported: {path}")


if __name__ == "__main__":
    main()
