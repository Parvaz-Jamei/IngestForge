from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T")


class ProviderRegistry:
    def __init__(self) -> None:
        self.ai: dict[str, type[Any]] = {}
        self.search: dict[str, type[Any]] = {}
        self.destination: dict[str, type[Any]] = {}

    def register_ai(self, name: str, cls: type[Any]) -> None:
        self.ai[name] = cls

    def register_search(self, name: str, cls: type[Any]) -> None:
        self.search[name] = cls

    def register_destination(self, name: str, cls: type[Any]) -> None:
        self.destination[name] = cls

    def get_ai(self, name: str) -> type[Any]:
        return self.ai[name]

    def get_search(self, name: str) -> type[Any]:
        return self.search[name]

    def get_destination(self, name: str) -> type[Any]:
        return self.destination[name]


registry = ProviderRegistry()
