"""Tests for proxy and user-agent rotation."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from form_crawler.proxy.rotation import ProxyRotator, UserAgentRotator


@pytest.fixture
def proxy_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("http://user:pass@proxy1.com:8080\n")
        f.write("socks5://proxy2.com:1080\n")
        f.write("# comment line\n")
        f.write("proxy3.com:3128\n")
        f.write("\n")
        return Path(f.name)


def test_load_proxies_from_file(proxy_file):
    rotator = ProxyRotator(proxy_file)
    assert rotator.has_proxies
    assert rotator.available_count == 3


def test_no_proxies():
    rotator = ProxyRotator()
    assert not rotator.has_proxies
    assert rotator.available_count == 0


@pytest.mark.asyncio
async def test_get_proxy(proxy_file):
    rotator = ProxyRotator(proxy_file)
    proxy = await rotator.get_proxy()
    assert proxy is not None
    assert "proxy" in proxy


@pytest.mark.asyncio
async def test_proxy_ban_after_failures(proxy_file):
    rotator = ProxyRotator(proxies=["http://bad:8080"])
    for _ in range(6):
        await rotator.report_failure("http://bad:8080")
    assert rotator.available_count == 0


@pytest.mark.asyncio
async def test_proxy_ban_resets():
    rotator = ProxyRotator(proxies=["http://only:8080"])
    for _ in range(6):
        await rotator.report_failure("http://only:8080")
    # All banned, but get_proxy should reset
    proxy = await rotator.get_proxy()
    assert proxy is not None


def test_user_agent_rotator():
    rotator = UserAgentRotator()
    ua = rotator.get_random()
    assert "Mozilla" in ua


def test_user_agent_round_robin():
    agents = ["UA1", "UA2", "UA3"]
    rotator = UserAgentRotator(custom_agents=agents)
    assert rotator.get_next() == "UA1"
    assert rotator.get_next() == "UA2"
    assert rotator.get_next() == "UA3"
    assert rotator.get_next() == "UA1"


def test_playwright_proxy_format(proxy_file):
    rotator = ProxyRotator(proxy_file)
    result = rotator.get_playwright_proxy("http://user:pass@proxy1.com:8080")
    assert result["server"] == "http://proxy1.com:8080"
    assert result["username"] == "user"
    assert result["password"] == "pass"
