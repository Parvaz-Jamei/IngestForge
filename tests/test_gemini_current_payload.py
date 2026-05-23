from __future__ import annotations

import json

from ingestforge.core.contracts import EvidenceBundle
from ingestforge.providers.ai.gemini_provider import GeminiProvider
from ingestforge.providers.ai.schema_repair import sanitize_schema_for_gemini


def test_current_gemini_payload_uses_response_format_text_mime_type():
    payload = GeminiProvider(model="any-configured-model").build_payload(
        EvidenceBundle(clean_text="x"), {"type": "object", "properties": {}}
    )
    text = payload["generationConfig"]["responseFormat"]["text"]
    assert text["mimeType"] == "application/json"
    assert text["schema"] == {"type": "object", "properties": {}}
    assert "responseMimeType" not in payload["generationConfig"]


def test_legacy_gemini_payload_only_when_explicit_api_style():
    payload = GeminiProvider(
        model="any-configured-model", api_style="legacy_response_schema"
    ).build_payload(EvidenceBundle(clean_text="x"), {"type": "object", "properties": {}})
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert payload["generationConfig"]["responseSchema"] == {"type": "object", "properties": {}}
    assert "responseFormat" not in payload["generationConfig"]


def test_gemini_schema_sanitizer_expands_defs_and_removes_unsupported_features():
    schema = {
        "$defs": {
            "Thing": {
                "type": "object",
                "title": "Thing",
                "default": {},
                "additionalProperties": False,
                "properties": {"name": {"type": "string", "examples": ["a"]}},
            }
        },
        "type": "object",
        "properties": {"thing": {"$ref": "#/$defs/Thing"}},
    }
    sanitized = sanitize_schema_for_gemini(schema)
    dumped = json.dumps(sanitized)
    assert "$ref" not in dumped
    assert "$defs" not in dumped
    assert "default" not in dumped
    assert "examples" not in dumped
    assert "additionalProperties" not in dumped
