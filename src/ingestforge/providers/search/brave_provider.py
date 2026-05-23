from __future__ import annotations

import os

import httpx

from ingestforge.core.errors import ConfigError
from ingestforge.providers.fetch.safe_url import host_allowed, validate_public_url
from ingestforge.providers.search.base import SearchProvider, SearchQuery, SearchResult


class BraveSearchProvider(SearchProvider):
    provider_id = "brave"

    def __init__(self, *, api_key: str | None = None, timeout_seconds: float = 15.0) -> None:
        self.api_key = api_key or os.getenv("INGESTFORGE_BRAVE_API_KEY")
        self.timeout_seconds = timeout_seconds

    def search(
        self,
        query: str | SearchQuery,
        *,
        max_results: int = 10,
        domains: list[str] | None = None,
    ) -> list[SearchResult]:
        q = (
            query
            if isinstance(query, SearchQuery)
            else SearchQuery(query=query, max_results=max_results, allowed_domains=domains or [])
        )
        if not self.api_key:
            raise ConfigError("Brave Search API key is required: INGESTFORGE_BRAVE_API_KEY")
        headers = {"Accept": "application/json", "X-Subscription-Token": self.api_key}
        params: dict[str, str | int] = {"q": q.query, "count": q.max_results}
        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.get(
                "https://api.search.brave.com/res/v1/web/search", headers=headers, params=params
            )
        if resp.status_code >= 400:
            raise ConfigError(f"Brave Search failed with HTTP {resp.status_code}")
        data = resp.json()
        raw_results = (data.get("web") or {}).get("results") or []
        out: list[SearchResult] = []
        seen: set[str] = set()
        for item in raw_results:
            url = str(item.get("url") or "")
            try:
                safe = validate_public_url(url)
            except Exception:
                continue
            if not host_allowed(safe, q.allowed_domains, q.denied_domains, True):
                continue
            if safe in seen:
                continue
            seen.add(safe)
            out.append(
                SearchResult(
                    url=safe,
                    title=item.get("title"),
                    snippet=item.get("description"),
                    source_provider=self.provider_id,
                    rank=len(out) + 1,
                    score=item.get("page_age") if isinstance(item.get("page_age"), float) else None,
                    raw=item,
                )
            )
            if len(out) >= q.max_results:
                break
        return out
