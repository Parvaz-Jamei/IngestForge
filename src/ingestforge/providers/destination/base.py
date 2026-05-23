from __future__ import annotations

from abc import ABC, abstractmethod

from ingestforge.core.contracts import StandardPackage


class DestinationAdapter(ABC):
    @abstractmethod
    def publish(self, package: StandardPackage) -> dict:
        raise NotImplementedError
