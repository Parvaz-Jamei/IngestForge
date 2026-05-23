from ingestforge.providers.search.base import SearchProvider, SearchQuery, SearchResult


class TavilySearchProvider(SearchProvider):
    provider_id = "tavily"

    def search(
        self, query: str | SearchQuery, *, max_results: int = 10, domains: list[str] | None = None
    ) -> list[SearchResult]:
        raise RuntimeError("Configure Tavily API key before live use; CI uses mocked providers")
