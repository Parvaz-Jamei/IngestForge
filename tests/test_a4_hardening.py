from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestforge.core.config import DestinationConfig, EndpointConfig, config_sha256, load_profile
from ingestforge.core.contracts import (
    ArticleObject,
    EvidenceBundle,
    MultilingualText,
    SourceRef,
    StandardPackage,
)
from ingestforge.core.errors import ConfigError, DestinationError, ValidationFailure
from ingestforge.datasets.writer import DatasetWriter
from ingestforge.providers.ai.deepseek_provider import DeepSeekProvider
from ingestforge.providers.ai.gemini_provider import GeminiProvider
from ingestforge.providers.ai.openai_provider import OpenAIProvider
from ingestforge.providers.ai.schema_repair import sanitize_schema_for_gemini, strict_openai_schema
from ingestforge.providers.destination.generic_rest import GenericRestDestination
from ingestforge.providers.search.brave_provider import BraveSearchProvider
from ingestforge.security.redaction import redact_secrets


def test_profile_extends_and_hash():
    p = load_profile("profiles/dataset_only.yaml")
    assert p.profile_name == "dataset_only"
    assert len(config_sha256(p)) == 64


def test_extra_config_is_rejected(tmp_path: Path):
    profile = tmp_path / "bad.yaml"
    profile.write_text("profile_name: bad\nunknown: true\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_profile(profile)


def test_flat_env_provider_specific_model_resolution(monkeypatch):
    monkeypatch.setenv("INGESTFORGE_AI_PROVIDER", "openai")
    monkeypatch.setenv("INGESTFORGE_OPENAI_MODEL", "env-openai-model")
    p = load_profile(
        "profiles/manual_safe.yaml", overrides={"pipeline": {"external_calls": "ai_only"}}
    )
    assert p.ai.provider == "openai"
    assert p.ai.model == "env-openai-model"


def test_openai_schema_recursive_additional_properties_false():
    schema = {
        "type": "object",
        "properties": {"outer": {"type": "object", "properties": {"x": {"type": "string"}}}},
    }
    out = strict_openai_schema(schema)
    assert out["additionalProperties"] is False
    assert out["properties"]["outer"]["additionalProperties"] is False
    assert schema.get("additionalProperties") is None


def test_openai_schema_rejects_refs():
    with pytest.raises(ValidationFailure):
        strict_openai_schema({"$ref": "#/$defs/X", "$defs": {"X": {"type": "object"}}})


def test_openai_payload_contract():
    payload = OpenAIProvider(model="configured-model", max_output_tokens=12).build_payload(
        EvidenceBundle(clean_text="x"), {"type": "object", "properties": {}}
    )
    assert payload["model"] == "configured-model"
    assert payload["store"] is False
    assert payload["text"]["format"]["strict"] is True


def test_deepseek_payload_contract():
    payload = DeepSeekProvider(model="deepseek-model", max_output_tokens=22).build_payload(
        EvidenceBundle(clean_text="x")
    )
    assert payload["model"] == "deepseek-model"
    assert payload["response_format"] == {"type": "json_object"}
    assert "JSON" in payload["messages"][0]["content"]
    assert payload["thinking"] == {"type": "disabled"}


def test_gemini_schema_inlines_refs_and_payload_is_json():
    schema = {
        "$defs": {
            "Name": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
        },
        "type": "object",
        "properties": {"name": {"$ref": "#/$defs/Name"}},
    }
    sanitized = sanitize_schema_for_gemini(schema)
    assert "$ref" not in json.dumps(sanitized)
    payload = GeminiProvider(model="gemini-model").build_payload(
        EvidenceBundle(clean_text="x"), schema
    )
    assert payload["generationConfig"]["responseFormat"]["text"]["mimeType"] == "application/json"
    assert payload["generationConfig"]["responseFormat"]["text"]["schema"]


def test_dataset_flags_control_outputs(tmp_path: Path):
    p = StandardPackage(
        source_refs=[SourceRef(url="https://example.com/a", source_hash="s1")],
        article=ArticleObject(
            title=MultilingualText(en="T"), body=MultilingualText(en="body " * 30)
        ),
    )
    cfg = load_profile("profiles/manual_safe.yaml").dataset.model_copy(
        update={"write_chunks": False, "write_clean": False}
    )
    run_dir = DatasetWriter(tmp_path, config=cfg).write_package(p)
    assert (run_dir / "package.json").exists()
    assert not (run_dir / "chunks/rag_chunks.jsonl").exists()
    assert not (run_dir / "clean/articles.jsonl").exists()


def test_generic_rest_template_undefined_fails():
    cfg = DestinationConfig(
        provider="generic_rest",
        base_url="https://example.com/api",
        endpoints={"create_content": EndpointConfig(path="/content")},
        payload_templates={"create_content": {"bad": "{{ article.missing.value }}"}},
    )
    with pytest.raises(DestinationError):
        GenericRestDestination(cfg).build_payload(StandardPackage())


def test_generic_rest_missing_content_id_fails(monkeypatch):
    cfg = DestinationConfig(
        provider="generic_rest",
        base_url="https://example.com/api",
        endpoints={
            "create_content": EndpointConfig(path="/content"),
            "verify": EndpointConfig(method="GET", path="/content/{content_id}"),
        },
    )

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        text = "{}"

        def json(self):
            return {"ok": True}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("ingestforge.providers.destination.generic_rest.httpx.Client", FakeClient)
    with pytest.raises(DestinationError):
        GenericRestDestination(cfg).publish(StandardPackage())


def test_redaction_removes_bearer_and_query_key():
    text = "Authorization: Bearer abcdefghijklmnop https://x.test?a=1&api_key=SECRET123"
    redacted = redact_secrets(text)
    assert "abcdefghijklmnop" not in redacted
    assert "SECRET123" not in redacted


def test_brave_provider_filters_and_deduplicates(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "web": {
                    "results": [
                        {"url": "https://example.com/a?x=1", "title": "A"},
                        {"url": "https://www.iana.org/b", "title": "B"},
                        {"url": "http://127.0.0.1/internal", "title": "Bad"},
                        {"url": "https://example.com/a?x=1", "title": "Dup"},
                    ]
                }
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setenv("INGESTFORGE_BRAVE_API_KEY", "demo")
    monkeypatch.setattr("ingestforge.providers.search.brave_provider.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "ingestforge.providers.search.brave_provider.validate_public_url", lambda url: url
    )
    results = BraveSearchProvider().search("topic", max_results=10, domains=["example.com"])
    assert [r.url for r in results] == ["https://example.com/a?x=1"]
