import pytest

from ingestforge.core.contracts import EvidenceBundle
from ingestforge.providers.ai.deepseek_provider import DeepSeekProvider
from ingestforge.providers.ai.gemini_provider import GeminiProvider
from ingestforge.providers.ai.mock_provider import MockAIProvider
from ingestforge.providers.ai.openai_provider import OpenAIProvider
from ingestforge.providers.ai.schema_repair import (
    parse_strict_json,
    sanitize_json_schema_for_provider,
)


def test_mock_provider_builds_article():
    article = MockAIProvider(model="mock").build_article(
        EvidenceBundle(page_title="T", clean_text="Body text")
    )
    assert article.title.en == "T"


def test_openai_payload_store_false():
    payload = OpenAIProvider(model="model", max_output_tokens=123).build_payload(
        EvidenceBundle(clean_text="x"), {"type": "object"}
    )
    assert payload["store"] is False and payload["max_output_tokens"] == 123


def test_deepseek_json_mode_payload():
    payload = DeepSeekProvider(model="model").build_payload(EvidenceBundle(clean_text="x"))
    assert payload["response_format"]["type"] == "json_object"


def test_gemini_payload_json():
    payload = GeminiProvider(model="model").build_payload(
        EvidenceBundle(clean_text="x"), {"type": "object", "title": "X"}
    )
    text_format = payload["generationConfig"]["responseFormat"]["text"]
    assert text_format["mimeType"] == "application/json"
    assert text_format["schema"]["type"] == "object"


def test_strict_json_rejects_trailing_text():
    with pytest.raises(ValueError):
        parse_strict_json('{"a":1} trailing')


def test_schema_sanitizer_removes_default():
    out = sanitize_json_schema_for_provider(
        {"type": "object", "default": {}, "properties": {"x": {"default": 1}}}, "openai"
    )
    assert "default" not in str(out)
