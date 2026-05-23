from __future__ import annotations

from ingestforge.core.contracts import (
    ArticleObject,
    EvidenceBundle,
    MultilingualText,
    ProviderCapabilities,
)
from ingestforge.providers.ai.base import AIProvider


class MockAIProvider(AIProvider):
    provider_id = "mock"
    capabilities = ProviderCapabilities(
        structured_output="json_schema_strict", supports_vision=True, live_calls_enabled=True
    )

    def build_article(self, evidence: EvidenceBundle, schema: dict | None = None) -> ArticleObject:
        title = evidence.page_title or "Ingested source package"
        body = evidence.clean_text[:3000] or "No extracted text was available."
        return ArticleObject(
            title=MultilingualText.from_languages(self.target_languages, title),
            description=MultilingualText.from_languages(self.target_languages, body[:280]),
            body=MultilingualText.from_languages(self.target_languages, body),
            tags=["ingestion", "dataset"],
            tags_text="ingestion, dataset",
            seo={"title": title, "description": body[:150]},
            domain_meta={
                "provider": self.provider_id,
                "model": self.model,
                "prompt_version": self.prompt.version,
                "prompt_sha256": self.prompt.sha256,
            },
        )

    def rank_image(self, image, context=None):
        score = 0.65
        if getattr(image, "width", 0) and getattr(image, "height", 0):
            score += 0.1
        return {
            "is_relevant": score >= 0.6,
            "image_type": "photo",
            "contains_useful_text": False,
            "quality_score": min(score, 1.0),
            "risk_flags": [],
            "reason": "mock vision result",
        }
