"""Proxy and user-agent rotation with health tracking."""

import random
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from ..config.constants import USER_AGENTS

logger = logging.getLogger(__name__)


@dataclass
class ProxyEntry:
    """A proxy with health stats."""
    url: str
    failures: int = 0
    successes: int = 0
    is_banned: bool = False
    last_used: float = 0.0

    @property
    def score(self) -> float:
        total = self.successes + self.failures
        if total == 0:
            return 0.5
        return self.successes / total


class ProxyRotator:
    """Rotates through a pool of proxies, tracking health."""

    def __init__(self, proxy_file: Optional[Path] = None, proxies: Optional[list[str]] = None):
        self._proxies: list[ProxyEntry] = []
        self._lock = asyncio.Lock()

        if proxies:
            for p in proxies:
                self._proxies.append(ProxyEntry(url=p.strip()))
        elif proxy_file and proxy_file.exists():
            self._load_from_file(proxy_file)

    def _load_from_file(self, path: Path):
        """Load proxies from file. Format: protocol://user:pass@host:port or host:port."""
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Normalize
                    if not line.startswith(("http://", "https://", "socks5://", "socks4://")):
                        line = f"http://{line}"
                    self._proxies.append(ProxyEntry(url=line))
        logger.info(f"Loaded {len(self._proxies)} proxies")

    @property
    def has_proxies(self) -> bool:
        return len(self._proxies) > 0

    @property
    def available_count(self) -> int:
        return sum(1 for p in self._proxies if not p.is_banned)

    async def get_proxy(self) -> Optional[str]:
        """Get next proxy using weighted random selection."""
        async with self._lock:
            available = [p for p in self._proxies if not p.is_banned]
            if not available:
                # Reset all bans if everything is banned
                if self._proxies:
                    for p in self._proxies:
                        p.is_banned = False
                        p.failures = 0
                    available = self._proxies
                else:
                    return None

            # Weighted selection by score
            weights = [max(p.score, 0.1) for p in available]
            chosen = random.choices(available, weights=weights, k=1)[0]
            chosen.last_used = asyncio.get_event_loop().time()
            return chosen.url

    async def report_success(self, proxy_url: str):
        """Mark a proxy as successfully used."""
        async with self._lock:
            for p in self._proxies:
                if p.url == proxy_url:
                    p.successes += 1
                    break

    async def report_failure(self, proxy_url: str):
        """Mark a proxy as failed. Ban after 5 consecutive failures."""
        async with self._lock:
            for p in self._proxies:
                if p.url == proxy_url:
                    p.failures += 1
                    if p.failures >= 5 and p.score < 0.3:
                        p.is_banned = True
                        logger.warning(f"Proxy banned: {proxy_url}")
                    break

    def get_playwright_proxy(self, proxy_url: str) -> dict:
        """Convert proxy URL to Playwright proxy format."""
        from urllib.parse import urlparse
        parsed = urlparse(proxy_url)
        proxy_dict = {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port or 8080}",
        }
        if parsed.username:
            proxy_dict["username"] = parsed.username
        if parsed.password:
            proxy_dict["password"] = parsed.password
        return proxy_dict


class UserAgentRotator:
    """Rotates user agents."""

    def __init__(self, custom_agents: Optional[list[str]] = None):
        self._agents = custom_agents or USER_AGENTS.copy()
        self._index = 0

    def get_random(self) -> str:
        """Get a random user agent."""
        return random.choice(self._agents)

    def get_next(self) -> str:
        """Get next user agent in round-robin."""
        agent = self._agents[self._index % len(self._agents)]
        self._index += 1
        return agent
