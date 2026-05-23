from __future__ import annotations

import os
from typing import Any

from ingestforge.core.contracts import ArticleObject, EvidenceBundle, ProviderCapabilities
from ingestforge.providers.ai.base import AIProvider
from ingestforge.providers.ai.schema_repair import parse_strict_json, strict_openai_schema


class OpenAIProvider(AIProvider):
    provider_id = "openai"
    capabilities = ProviderCapabilities(
        structured_output="json_schema_strict",
        supports_vision=True,
        supports_tools=True,
        live_calls_enabled=False,
    )

    def build_payload(self, evidence: EvidenceBundle, schema: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self.prompt_instruction(),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": str(
                                evidence.compact(self.options.get("max_input_chars", 30000))
                            ),
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "article_draft",
                    "strict": True,
                    "schema": strict_openai_schema(schema),
                }
            },
            "temperature": self.options.get("temperature", 0.1),
            "max_output_tokens": self.options.get("max_output_tokens", 3000),
            "store": False,
        }

    def build_article(
        self, evidence: EvidenceBundle, schema: dict[str, Any] | None = None
    ) -> ArticleObject:
        if self.options.get("mock_response"):
            return ArticleObject.model_validate(
                parse_strict_json(str(self.options["mock_response"]))
            )
        if not os.getenv("INGESTFORGE_OPENAI_API_KEY"):
            raise RuntimeError(
                "OpenAI API key is not configured; use mock provider for offline runs"
            )
        raise RuntimeError(
            "Live OpenAI calls are optional and not executed in the alpha core build"
        )
