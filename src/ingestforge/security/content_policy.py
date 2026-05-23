from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ingestforge.core.contracts import AssetRecord, SourceRef, StandardPackage


@dataclass(frozen=True)
class PolicyDecision:
    license_status: str = "needs_review"
    human_review_required: bool = True
    publish_allowed: bool = False
    risk_flags: tuple[str, ...] = ("license_not_verified",)
    notes: str = "IngestForge does not grant copyright permission; external sources require review."


class ContentPolicy(Protocol):
    def classify_source(self, source: SourceRef) -> PolicyDecision: ...

    def classify_asset(self, asset: AssetRecord) -> PolicyDecision: ...

    def requires_human_review(self, package: StandardPackage) -> bool: ...


class ConservativeContentPolicy:
    def classify_source(self, source: SourceRef) -> PolicyDecision:
        flags = tuple([*source.risk_flags, "needs_license_review"])
        return PolicyDecision(license_status="needs_review", risk_flags=flags)

    def classify_asset(self, asset: AssetRecord) -> PolicyDecision:
        flags = tuple([*asset.risk_flags, "asset_needs_license_review"])
        return PolicyDecision(license_status="needs_review", risk_flags=flags)

    def requires_human_review(self, package: StandardPackage) -> bool:
        return True


def default_policy() -> ContentPolicy:
    return ConservativeContentPolicy()


def default_license_status() -> str:
    return "needs_review"


def requires_human_review() -> bool:
    return True
