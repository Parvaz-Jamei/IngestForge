from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ingestforge.core.contracts import ArticleObject, EvidenceBundle, ProviderCapabilities
from ingestforge.core.prompts import PromptTemplate, resolve_prompt


class AIProvider(ABC):
    provider_id = "base"
    capabilities = ProviderCapabilities()

    def __init__(self, model: str = "", **kwargs: Any) -> None:
        from ingestforge.core.languages import normalize_source_language, parse_language_list

        self.model = model
        self.options = kwargs
        self.source_language = normalize_source_language(str(kwargs.get("source_language", "auto")))
        self.target_languages = parse_language_list(
            kwargs.get("target_languages", ["en"]), field_name="ai.target_languages"
        )
        self.prompt: PromptTemplate = resolve_prompt(
            str(kwargs.get("prompt_version", "article_builder.v1"))
        )

    def prompt_instruction(self) -> str:
        return self.prompt.render(
            source_language=self.source_language,
            target_languages=", ".join(self.target_languages),
        )

    @abstractmethod
    def build_article(
        self, evidence: EvidenceBundle, schema: dict[str, Any] | None = None
    ) -> ArticleObject:
        raise NotImplementedError

    def rank_image(self, image: Any, context: EvidenceBundle | None = None) -> dict[str, Any]:
        return {
            "is_relevant": True,
            "image_type": "unknown",
            "contains_useful_text": False,
            "quality_score": 0.5,
            "risk_flags": ["ai_vision_not_configured"],
            "reason": "local fallback ranker",
        }
