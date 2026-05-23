from __future__ import annotations

from ingestforge.providers.fetch.safe_url import normalize_url
from ingestforge.providers.search.base import SearchProvider, SearchQuery, SearchResult


class ManualSearchProvider(SearchProvider):
    provider_id = "manual"

    def search(
        self,
        query: str | SearchQuery,
        *,
        max_results: int = 10,
        domains: list[str] | None = None,
    ) -> list[SearchResult]:
        q = query.query if isinstance(query, SearchQuery) else query
        limit = query.max_results if isinstance(query, SearchQuery) else max_results
        urls = [u.strip() for u in q.split() if u.startswith(("http://", "https://"))]
        seen: set[str] = set()
        out: list[SearchResult] = []
        for u in urls:
            norm = normalize_url(u)
            if norm in seen:
                continue
            seen.add(norm)
            out.append(
                SearchResult(
                    url=norm,
                    title=norm,
                    source_provider=self.provider_id,
                    rank=len(out) + 1,
                    score=1.0 / (len(out) + 1),
                )
            )
            if len(out) >= limit:
                break
        return out
