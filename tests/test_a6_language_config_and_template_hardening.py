from __future__ import annotations

import pytest

from ingestforge.core.config import DestinationConfig, load_profile
from ingestforge.core.contracts import ArticleObject, MultilingualText, SourceRef, StandardPackage
from ingestforge.core.errors import ConfigError
from ingestforge.datasets.chunker import build_rag_records
from ingestforge.datasets.data_card import build_dataset_card
from ingestforge.providers.ai.deepseek_provider import DeepSeekProvider
from ingestforge.providers.destination.generic_rest import GenericRestDestination


def test_target_languages_accept_bcp47_style_tags_without_allowlist():
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={
            "ai": {"source_language": "auto", "target_languages": ["de", "pt-BR", "zh-Hant"]}
        },
    )
    assert profile.ai.target_languages == ["de", "pt-BR", "zh-Hant"]


def test_target_languages_can_be_overridden_from_comma_env(monkeypatch):
    monkeypatch.setenv("INGESTFORGE_TARGET_LANGUAGES", "ar,de,es-419")
    profile = load_profile("profiles/strict_industrial.yaml")
    assert profile.ai.target_languages == ["ar", "de", "es-419"]


def test_unknown_or_empty_language_tags_fail_clearly():
    with pytest.raises(ConfigError) as exc:
        load_profile(
            "profiles/strict_industrial.yaml", overrides={"ai": {"target_languages": [""]}}
        )
    assert "ai.target_languages" in str(exc.value)


def test_provider_prompt_contains_configured_target_languages():
    payload = DeepSeekProvider(
        model="m",
        source_language="auto",
        target_languages=["de", "pt-BR"],
    ).build_payload(StandardPackage().evidence_bundle)
    prompt = payload["messages"][0]["content"]
    assert "Target output language tags: de, pt-BR" in prompt
    assert "Do not hard-code fa/en" in prompt


def test_article_object_dataset_and_card_support_dynamic_languages():
    package = StandardPackage(
        source_refs=[SourceRef(url="https://example.com", license_status="allowed")],
        article=ArticleObject(
            title=MultilingualText.model_validate({"de": "Titel", "pt-BR": "Título"}),
            body=MultilingualText.model_validate(
                {"de": "eins zwei drei " * 30, "pt-BR": "um dois três " * 30}
            ),
        ),
    )
    report = package.validate_package()
    assert report.is_valid
    records = build_rag_records(
        package, chunk_unit="words", tokenizer="words", chunk_size=20, chunk_overlap=0
    )
    languages = {
        record.language for record in records if record.record_stage == "generated_article"
    }
    assert {"de", "pt-BR"}.issubset(languages)
    assert build_dataset_card(package)["language_coverage"] == ["de", "pt-BR"]


def test_destination_templates_can_reference_hyphenated_language_tags():
    package = StandardPackage(
        article=ArticleObject(title=MultilingualText.model_validate({"pt-BR": "Título"}))
    )
    dest = GenericRestDestination(
        DestinationConfig(
            provider="generic_rest",
            payload_templates={"create_content": {"title": "{{ article.title.pt-BR }}"}},
        )
    )
    assert dest.build_payload(package)["title"] == "Título"


def test_empty_allowed_domain_in_template_fails_clearly(monkeypatch):
    monkeypatch.delenv("INGESTFORGE_ALLOWED_DOMAIN", raising=False)
    with pytest.raises(ConfigError) as exc:
        load_profile("profiles/examples/strict_live_template.yaml")
    assert "allowed_domains" in str(exc.value)


def test_strict_live_template_without_ai_provider_fails_clearly(monkeypatch):
    monkeypatch.setenv("INGESTFORGE_ALLOWED_DOMAIN", "example.com")
    monkeypatch.delenv("INGESTFORGE_AI_PROVIDER", raising=False)
    monkeypatch.delenv("INGESTFORGE_AI_MODEL", raising=False)
    with pytest.raises(ConfigError) as exc:
        load_profile("profiles/examples/strict_live_template.yaml")
    assert "ai.provider" in str(exc.value)


def test_provider_name_is_normalized_to_lowercase(monkeypatch):
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={"ai": {"provider": "OpenAI", "model": "any-model"}},
    )
    assert profile.ai.provider == "openai"
