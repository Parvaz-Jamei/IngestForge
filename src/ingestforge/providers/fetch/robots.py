from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from ingestforge.core.config import FetchConfig
from ingestforge.providers.fetch.safe_url import validate_public_url


@dataclass
class _CacheItem:
    parser: urllib.robotparser.RobotFileParser
    expires_at: float


class RobotsPolicy:
    def __init__(self, fetch: FetchConfig | str = "IngestForge") -> None:
        if isinstance(fetch, FetchConfig):
            self.user_agent = fetch.user_agent
            self.fetch = fetch
        else:
            self.user_agent = fetch
            self.fetch = FetchConfig(user_agent=fetch)
        self._cache: dict[str, _CacheItem] = {}

    def allowed(self, url: str) -> bool:
        if self.fetch.robots_policy == "ignore_for_manual":
            return True
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        base_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            safe_base = validate_public_url(
                base_url,
                deny_private_networks=self.fetch.deny_private_networks,
                require_https=self.fetch.require_https,
            )
        except Exception:
            return self.fetch.robots_policy == "fail_open"
        now = time.time()
        item = self._cache.get(safe_base)
        if item and item.expires_at > now:
            return bool(item.parser.can_fetch(self.user_agent, url))
        parser = urllib.robotparser.RobotFileParser(safe_base)
        try:
            headers = {"User-Agent": self.user_agent, "Accept": "text/plain,*/*;q=0.1"}
            with (
                httpx.Client(timeout=self.fetch.timeout_seconds, follow_redirects=False) as client,
                client.stream("GET", safe_base, headers=headers) as resp,
            ):
                if resp.status_code in {404, 410}:
                    parser.parse([])
                    self._cache[safe_base] = _CacheItem(
                        parser, now + self.fetch.robots_cache_ttl_seconds
                    )
                    return True
                if not (200 <= resp.status_code < 300):
                    return self.fetch.robots_policy == "fail_open"
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > self.fetch.max_robots_bytes:
                        return self.fetch.robots_policy == "fail_open"
                    chunks.append(chunk)
            parser.parse(b"".join(chunks).decode("utf-8", errors="replace").splitlines())
        except Exception:
            return self.fetch.robots_policy == "fail_open"
        self._cache[safe_base] = _CacheItem(parser, now + self.fetch.robots_cache_ttl_seconds)
        return bool(parser.can_fetch(self.user_agent, url))
