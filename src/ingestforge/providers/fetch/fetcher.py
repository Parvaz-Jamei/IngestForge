from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from ingestforge.core.config import FetchConfig, SearchConfig
from ingestforge.core.errors import FetchError
from ingestforge.providers.fetch.encoding import decode_response_bytes
from ingestforge.providers.fetch.robots import RobotsPolicy
from ingestforge.providers.fetch.safe_url import host_allowed, validate_public_url


@dataclass
class FetchedDocument:
    url: str
    final_url: str
    status_code: int
    content_type: str
    text: str
    bytes_read: int
    robots_allowed: bool | None
    encoding_used: str | None = None
    decode_replacement_count: int = 0


class SafeFetcher:
    def __init__(self, fetch: FetchConfig, search: SearchConfig) -> None:
        self.fetch = fetch
        self.search = search
        self.robots = RobotsPolicy(fetch)

    def fetch_html(self, url: str) -> FetchedDocument:
        current = validate_public_url(
            url,
            deny_private_networks=self.fetch.deny_private_networks,
            require_https=self.fetch.require_https,
        )
        if not host_allowed(
            current,
            self.search.allowed_domains,
            self.search.denied_domains,
            self.search.allow_subdomains,
        ):
            raise FetchError("URL is not allowed by domain policy")
        if self.search.obey_robots_txt and not self.robots.allowed(current):
            raise FetchError("robots.txt disallows URL")
        headers = {"User-Agent": self.fetch.user_agent, "Accept": "text/html,application/xhtml+xml"}
        with httpx.Client(timeout=self.fetch.timeout_seconds, follow_redirects=False) as client:
            for _ in range(self.fetch.max_redirects + 1):
                with client.stream("GET", current, headers=headers) as resp:
                    if resp.status_code in {301, 302, 303, 307, 308}:
                        loc = resp.headers.get("location")
                        if not loc:
                            raise FetchError("redirect without Location header")
                        current = validate_public_url(
                            urljoin(current, loc),
                            deny_private_networks=self.fetch.deny_private_networks,
                            require_https=self.fetch.require_https,
                        )
                        if not host_allowed(
                            current,
                            self.search.allowed_domains,
                            self.search.denied_domains,
                            self.search.allow_subdomains,
                        ):
                            raise FetchError("redirect target is not allowed by domain policy")
                        if self.search.obey_robots_txt and not self.robots.allowed(current):
                            raise FetchError("robots.txt disallows final redirect URL")
                        continue
                    if not (200 <= resp.status_code < 300):
                        raise FetchError(f"HTTP status not successful: {resp.status_code}")
                    ctype = resp.headers.get("content-type", "")
                    if "html" not in ctype.lower() and "text/plain" not in ctype.lower():
                        raise FetchError(f"non-HTML content type: {ctype}")
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in resp.iter_bytes():
                        total += len(chunk)
                        if total > self.fetch.max_html_bytes:
                            raise FetchError("HTML response exceeded max_html_bytes")
                        chunks.append(chunk)
                    data = b"".join(chunks)
                    decoded = decode_response_bytes(
                        data,
                        declared_encoding=resp.encoding,
                        content_type=ctype,
                    )
                    return FetchedDocument(
                        url=url,
                        final_url=current,
                        status_code=resp.status_code,
                        content_type=ctype,
                        text=decoded.text,
                        bytes_read=total,
                        robots_allowed=True,
                        encoding_used=decoded.encoding_used,
                        decode_replacement_count=decoded.replacement_count,
                    )
            raise FetchError("too many redirects")
