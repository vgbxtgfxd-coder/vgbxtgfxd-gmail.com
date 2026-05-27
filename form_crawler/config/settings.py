"""Application settings with environment variable support."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    """Global application settings."""

    # Paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)
    db_path: Path = field(default=None)
    export_dir: Path = field(default=None)
    log_dir: Path = field(default=None)

    # Crawler settings
    max_concurrent_tasks: int = 5
    request_timeout: int = 30
    page_load_timeout: int = 45
    retry_attempts: int = 3
    retry_delay: float = 2.0
    rate_limit_delay: float = 1.5  # seconds between requests to same domain
    max_pages_per_site: int = 15

    # Playwright
    headless: bool = True
    browser_type: str = "chromium"  # chromium, firefox, webkit
    viewport_width: int = 1920
    viewport_height: int = 1080

    # Proxy
    proxy_file: Path = field(default=None)
    proxy_rotation: bool = True

    # Search
    max_search_results: int = 50
    search_delay: float = 3.0  # delay between search queries

    # Export
    export_format: str = "csv"  # csv, xlsx, json

    # Logging
    log_level: str = "INFO"
    log_to_file: bool = True

    def __post_init__(self):
        if self.db_path is None:
            self.db_path = self.base_dir / "data" / "forms.db"
        if self.export_dir is None:
            self.export_dir = self.base_dir / "data" / "export"
        if self.log_dir is None:
            self.log_dir = self.base_dir / "data" / "logs"
        if self.proxy_file is None:
            self.proxy_file = self.base_dir / "config" / "proxies.txt"

        # Create directories
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        kwargs = {}
        env_map = {
            "CRAWLER_MAX_CONCURRENT": ("max_concurrent_tasks", int),
            "CRAWLER_TIMEOUT": ("request_timeout", int),
            "CRAWLER_PAGE_TIMEOUT": ("page_load_timeout", int),
            "CRAWLER_RETRY": ("retry_attempts", int),
            "CRAWLER_RATE_LIMIT": ("rate_limit_delay", float),
            "CRAWLER_HEADLESS": ("headless", lambda x: x.lower() in ("1", "true", "yes")),
            "CRAWLER_BROWSER": ("browser_type", str),
            "CRAWLER_LOG_LEVEL": ("log_level", str),
            "CRAWLER_EXPORT_FORMAT": ("export_format", str),
            "CRAWLER_DB_PATH": ("db_path", Path),
            "CRAWLER_EXPORT_DIR": ("export_dir", Path),
            "CRAWLER_LOG_DIR": ("log_dir", Path),
            "CRAWLER_PROXY_FILE": ("proxy_file", Path),
        }
        for env_key, (attr, converter) in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                kwargs[attr] = converter(val)
        return cls(**kwargs)
