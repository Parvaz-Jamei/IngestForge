from __future__ import annotations

from importlib import resources

import yaml

from ingestforge.core.config import load_profile
from ingestforge.core.contracts import EvidenceBundle
from ingestforge.core.provider_doctor import run_provider_doctor
from ingestforge.providers.ai.deepseek_provider import DeepSeekProvider
from ingestforge.providers.ai.gemini_provider import GeminiProvider
from ingestforge.providers.ai.openai_provider import OpenAIProvider


def test_offline_doctor_passes_for_mock_profile():
    profile = load_profile("profiles/strict_industrial.yaml")
    result = run_provider_doctor(profile)
    assert result["provider"] == "mock"
    assert result["payload_contract"] == "pass"
    assert result["live_smoke"] == "skipped"


def test_offline_doctor_validates_openai_payload():
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={
            "pipeline": {"external_calls": "ai_only"},
            "ai": {"provider": "openai", "model": "any-model"},
        },
    )
    assert run_provider_doctor(profile)["payload_contract"] == "pass"


def test_offline_doctor_validates_deepseek_payload():
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={
            "pipeline": {"external_calls": "ai_only"},
            "ai": {"provider": "deepseek", "model": "any-model"},
        },
    )
    assert run_provider_doctor(profile)["payload_contract"] == "pass"


def test_offline_doctor_validates_gemini_payload():
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={
            "pipeline": {"external_calls": "ai_only"},
            "ai": {"provider": "gemini", "model": "any-model"},
        },
    )
    assert run_provider_doctor(profile)["payload_contract"] == "pass"


def test_live_doctor_skips_without_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("INGESTFORGE_RUN_LIVE_PROVIDER_TESTS", raising=False)
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={
            "pipeline": {"external_calls": "ai_only"},
            "ai": {"provider": "openai", "model": "any-model"},
        },
    )
    result = run_provider_doctor(profile, live=True)
    assert result["live_smoke"] == "skipped"


def test_provider_contract_matrix_matches_capabilities():
    matrix = yaml.safe_load(
        resources.files("ingestforge").joinpath("provider_contracts.yaml").read_text()
    )
    assert matrix["openai"]["structured_output"] == OpenAIProvider.capabilities.structured_output
    assert (
        matrix["deepseek"]["structured_output"] == DeepSeekProvider.capabilities.structured_output
    )
    assert matrix["deepseek"]["thinking_control"] is True
    assert DeepSeekProvider.capabilities.supports_thinking_control is True
    assert matrix["gemini"]["structured_output"] == GeminiProvider.capabilities.structured_output


def test_live_doctor_runs_http_smoke_when_explicitly_enabled(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = '{"ok": true}'

        def json(self):
            return {"ok": True}

    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setenv("INGESTFORGE_RUN_LIVE_PROVIDER_TESTS", "1")
    monkeypatch.setenv("INGESTFORGE_OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("ingestforge.core.provider_doctor.httpx.post", fake_post)
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={
            "pipeline": {"external_calls": "ai_only"},
            "ai": {"provider": "openai", "model": "any-model"},
        },
    )
    result = run_provider_doctor(profile, live=True)
    assert result["live_smoke"] == "pass"
    assert calls
    assert calls[0][0].endswith("/responses")
    assert calls[0][1]["json"]["model"] == "any-model"


def test_live_doctor_reports_http_failure_without_raising_payload_error(monkeypatch):
    class FakeResponse:
        status_code = 401
        text = '{"error":"bad key"}'

        def json(self):
            return {"error": "bad key"}

    monkeypatch.setenv("INGESTFORGE_RUN_LIVE_PROVIDER_TESTS", "1")
    monkeypatch.setenv("INGESTFORGE_DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        "ingestforge.core.provider_doctor.httpx.post", lambda *a, **k: FakeResponse()
    )
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={
            "pipeline": {"external_calls": "ai_only"},
            "ai": {"provider": "deepseek", "model": "any-model"},
        },
    )
    result = run_provider_doctor(profile, live=True)
    assert result["payload_contract"] == "pass"
    assert result["live_smoke"] == "fail"
    assert any("HTTP 401" in warning for warning in result["warnings"])


def test_gemini_live_doctor_posts_generate_content_payload(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = '{"candidates": []}'

        def json(self):
            return {"candidates": []}

    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setenv("INGESTFORGE_RUN_LIVE_PROVIDER_TESTS", "1")
    monkeypatch.setenv("INGESTFORGE_GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("ingestforge.core.provider_doctor.httpx.post", fake_post)
    profile = load_profile(
        "profiles/strict_industrial.yaml",
        overrides={
            "pipeline": {"external_calls": "ai_only"},
            "ai": {"provider": "gemini", "model": "gemini-test-model"},
        },
    )
    result = run_provider_doctor(profile, live=True)
    assert result["live_smoke"] == "pass"
    assert calls[0][0].endswith("/models/gemini-test-model:generateContent")
    assert calls[0][1]["params"] == {"key": "test-key"}
    assert "model" not in calls[0][1]["json"]


def test_deepseek_thinking_enabled_omits_temperature_contract_noise():
    payload = DeepSeekProvider(model="any-model", thinking_enabled=True).build_payload(
        EvidenceBundle(clean_text="x"), {"type": "object", "properties": {}}
    )
    assert payload["thinking"] == {"type": "enabled"}
    assert "temperature" not in payload
