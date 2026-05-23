from __future__ import annotations

import json
import os
from typing import Any

from ingestforge.core.contracts import ArticleObject, EvidenceBundle, ProviderCapabilities
from ingestforge.providers.ai.base import AIProvider


class DeepSeekProvider(AIProvider):
    provider_id = "deepseek"
    capabilities = ProviderCapabilities(
        structured_output="json_object",
        supports_thinking_control=True,
        live_calls_enabled=False,
    )

    def build_payload(
        self, evidence: EvidenceBundle, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        thinking_enabled = bool(self.options.get("thinking_enabled"))
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": self.prompt_instruction(),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        evidence.compact(self.options.get("max_input_chars", 30000)),
                        ensure_ascii=False,
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": self.options.get("max_output_tokens", 3000),
            "thinking": {"type": "enabled" if thinking_enabled else "disabled"},
        }
        # DeepSeek documents that temperature/top_p/presence_penalty/frequency_penalty
        # have no effect in thinking mode. Keep temperature only for non-thinking mode
        # to avoid a misleading payload contract.
        if not thinking_enabled:
            payload["temperature"] = self.options.get("temperature", 0.1)
        return payload

    def build_openai_sdk_kwargs(
        self, evidence: EvidenceBundle, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        payload = self.build_payload(evidence, schema)
        thinking = payload.pop("thinking")
        return {**payload, "extra_body": {"thinking": thinking}}

    def build_article(
        self, evidence: EvidenceBundle, schema: dict[str, Any] | None = None
    ) -> ArticleObject:
        if not os.getenv("INGESTFORGE_DEEPSEEK_API_KEY"):
            raise RuntimeError(
                "DeepSeek API key is not configured; use mock provider for offline runs"
            )
        raise RuntimeError(
            "Live DeepSeek calls are optional and not executed in the alpha core build"
        )
