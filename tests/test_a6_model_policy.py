from __future__ import annotations

from pathlib import Path

import pytest

from ingestforge.core.config import ConfigError, load_profile


def test_strict_industrial_loads_offline_without_api_env(monkeypatch):
    for key in [
        "INGESTFORGE_OPENAI_MODEL",
        "INGESTFORGE_GEMINI_MODEL",
        "INGESTFORGE_DEEPSEEK_MODEL",
        "INGESTFORGE_AI_MODEL",
        "INGESTFORGE_OPENAI_API_KEY",
        "INGESTFORGE_GEMINI_API_KEY",
        "INGESTFORGE_DEEPSEEK_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)
    profile = load_profile("profiles/strict_industrial.yaml")
    assert profile.ai.provider == "mock"
    assert profile.ai.model == "mock"
    assert profile.pipeline.external_calls == "disabled"


@pytest.mark.parametrize("provider", ["openai", "gemini", "deepseek"])
def test_live_provider_missing_model_fails_when_external_ai_enabled(provider: str):
    with pytest.raises(ConfigError, match="ai.model must be set"):
        load_profile(
            "profiles/strict_industrial.yaml",
            overrides={
                "pipeline": {"external_calls": "ai_only"},
                "ai": {"provider": provider, "model": ""},
            },
        )


@pytest.mark.parametrize("provider", ["openai", "gemini", "deepseek"])
def test_live_provider_missing_model_allowed_when_external_ai_disabled(provider: str):
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={
            "pipeline": {"external_calls": "disabled"},
            "ai": {"provider": provider, "model": ""},
        },
    )
    assert profile.ai.provider == provider
    assert profile.ai.model == ""


def test_arbitrary_non_empty_model_string_is_accepted():
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={
            "pipeline": {"external_calls": "ai_only"},
            "ai": {"provider": "openai", "model": "future-provider-model-xyz"},
        },
    )
    assert profile.ai.model == "future-provider-model-xyz"


def test_provider_specific_env_model_precedes_generic(monkeypatch):
    monkeypatch.setenv("INGESTFORGE_OPENAI_MODEL", "provider-specific")
    monkeypatch.setenv("INGESTFORGE_AI_MODEL", "generic")
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={"pipeline": {"external_calls": "ai_only"}, "ai": {"provider": "openai"}},
    )
    assert profile.ai.model == "provider-specific"


def test_explicit_profile_model_precedes_env(monkeypatch):
    monkeypatch.setenv("INGESTFORGE_OPENAI_MODEL", "env-model")
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={
            "pipeline": {"external_calls": "ai_only"},
            "ai": {"provider": "openai", "model": "explicit-model"},
        },
    )
    assert profile.ai.model == "explicit-model"


def test_packaged_example_profile_paths_exist():
    for name in ["openai_live.yaml", "gemini_live.yaml", "deepseek_live.yaml"]:
        assert Path("profiles/examples", name).exists()
