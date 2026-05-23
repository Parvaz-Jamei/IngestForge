from __future__ import annotations

import os
from typing import Any

from ingestforge.core.contracts import ArticleObject, EvidenceBundle, ProviderCapabilities
from ingestforge.providers.ai.base import AIProvider
from ingestforge.providers.ai.schema_repair import sanitize_schema_for_gemini


class GeminiProvider(AIProvider):
    provider_id = "gemini"
    capabilities = ProviderCapabilities(
        structured_output="json_schema_subset", supports_vision=True, live_calls_enabled=False
    )

    def build_payload(self, evidence: EvidenceBundle, schema: dict[str, Any]) -> dict[str, Any]:
        api_style = self.options.get("api_style", "current_response_format")
        sanitized_schema = sanitize_schema_for_gemini(schema)
        generation_config: dict[str, Any] = {
            "temperature": self.options.get("temperature", 0.1),
            "maxOutputTokens": self.options.get("max_output_tokens", 3000),
        }
        if api_style == "legacy_response_schema":
            generation_config.update(
                {
                    "responseMimeType": "application/json",
                    "responseSchema": sanitized_schema,
                }
            )
        else:
            generation_config["responseFormat"] = {
                "text": {
                    "mimeType": "application/json",
                    "schema": sanitized_schema,
                }
            }
        return {
            "model": self.model,
            "systemInstruction": {"parts": [{"text": self.prompt_instruction()}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": str(evidence.compact(self.options.get("max_input_chars", 30000)))}
                    ],
                }
            ],
            "generationConfig": generation_config,
        }

    def build_python_sdk_config(self, schema: dict[str, Any]) -> dict[str, Any]:
        sanitized_schema = sanitize_schema_for_gemini(schema)
        if self.options.get("api_style", "current_response_format") == "legacy_response_schema":
            return {
                "response_mime_type": "application/json",
                "response_schema": sanitized_schema,
                "temperature": self.options.get("temperature", 0.1),
                "max_output_tokens": self.options.get("max_output_tokens", 3000),
            }
        return {
            "response_format": {
                "text": {
                    "mime_type": "application/json",
                    "schema": sanitized_schema,
                }
            },
            "temperature": self.options.get("temperature", 0.1),
            "max_output_tokens": self.options.get("max_output_tokens", 3000),
        }

    def build_article(
        self, evidence: EvidenceBundle, schema: dict[str, Any] | None = None
    ) -> ArticleObject:
        if not os.getenv("INGESTFORGE_GEMINI_API_KEY"):
            raise RuntimeError(
                "Gemini API key is not configured; use mock provider for offline runs. "
                "For live Gemini calls install: pip install ingestforge[gemini]"
            )
        try:
            import google.genai  # type: ignore[import-not-found]  # noqa: F401
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Gemini live provider requires: pip install ingestforge[gemini]"
            ) from exc
        raise RuntimeError(
            "Live Gemini calls are optional and not executed in the alpha core build"
        )
