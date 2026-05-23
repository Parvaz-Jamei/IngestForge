from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    query: str
    max_results: int = Field(default=10, ge=1, le=50)
    allowed_domains: list[str] = Field(default_factory=list)
    denied_domains: list[str] = Field(default_factory=list)
    language: str | None = None
    country: str | None = None
    freshness_days: int | None = None


class SearchResult(BaseModel):
    url: str
    title: str | None = None
    snippet: str | None = None
    source_provider: str = "manual"
    rank: int = 1
    score: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def provider(self) -> str:
        return self.source_provider


class SearchProvider(ABC):
    provider_id = "base"

    @abstractmethod
    def search(
        self,
        query: str | SearchQuery,
        *,
        max_results: int = 10,
        domains: list[str] | None = None,
    ) -> list[SearchResult]:
        raise NotImplementedError
