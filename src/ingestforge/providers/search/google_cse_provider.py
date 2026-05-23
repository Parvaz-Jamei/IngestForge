from ingestforge.providers.search.base import SearchProvider, SearchQuery, SearchResult


class GoogleCSESearchProvider(SearchProvider):
    provider_id = "google_cse"

    def search(
        self, query: str | SearchQuery, *, max_results: int = 10, domains: list[str] | None = None
    ) -> list[SearchResult]:
        raise RuntimeError(
            "Configure Google CSE credentials before live use; note current availability limits for new users"
        )
