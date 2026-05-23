from ingestforge.providers.search.base import SearchProvider, SearchQuery, SearchResult


class FirecrawlSearchProvider(SearchProvider):
    provider_id = "firecrawl"

    def search(
        self, query: str | SearchQuery, *, max_results: int = 10, domains: list[str] | None = None
    ) -> list[SearchResult]:
        raise RuntimeError("Configure Firecrawl API key before live use; CI uses mocked providers")
