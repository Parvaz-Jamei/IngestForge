from __future__ import annotations

import re

import pytest
from typer.testing import CliRunner

from ingestforge.cli import app
from ingestforge.core.config import load_profile
from ingestforge.core.contracts import EvidenceBundle
from ingestforge.core.errors import ConfigError
from ingestforge.core.prompts import prompt_registry, resolve_prompt
from ingestforge.providers.ai.deepseek_provider import DeepSeekProvider

runner = CliRunner()

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def test_prompt_version_resolves_to_packaged_template():
    prompt = resolve_prompt("article_builder.v1")
    assert prompt.resource_name == "article_builder.j2"
    assert prompt.template_name == "article_builder"
    assert prompt.sha256
    assert "article" in prompt.text.lower()
    assert "article_builder.v1" in prompt_registry.list_versions()


def test_unknown_prompt_version_fails_during_profile_load():
    with pytest.raises(ConfigError) as exc:
        load_profile(
            "profiles/strict_industrial.yaml",
            overrides={"ai": {"prompt_version": "missing_prompt.v1"}},
        )
    assert "unknown prompt version" in str(exc.value)


def test_provider_payload_uses_resolved_prompt_template():
    payload = DeepSeekProvider(model="model", prompt_version="article_builder.v1").build_payload(
        EvidenceBundle(clean_text="x")
    )
    rendered = payload["messages"][0]["content"]
    assert resolve_prompt("article_builder.v1").text.splitlines()[0] in rendered
    assert "Target output language tags: en" in rendered


def test_cli_help_has_clean_boolean_flags():
    ingest_help = runner.invoke(app, ["ingest-url", "--help"])
    assert ingest_help.exit_code == 0
    ingest_output = strip_ansi(ingest_help.output)
    assert "--no-external-calls" in ingest_output
    assert "--no-no-external-calls" not in ingest_output

    doctor_help = runner.invoke(app, ["doctor", "providers", "--help"])
    assert doctor_help.exit_code == 0
    doctor_output = strip_ansi(doctor_help.output)
    assert "--offline" in doctor_output
    assert "--no-offline" not in doctor_output


def test_doctor_offline_flag_overrides_live_flag(monkeypatch):
    calls = []

    def fake_post(*args, **kwargs):  # pragma: no cover - must not be called
        calls.append((args, kwargs))
        raise AssertionError("live smoke should not run when --offline is present")

    monkeypatch.setenv("INGESTFORGE_RUN_LIVE_PROVIDER_TESTS", "1")
    monkeypatch.setenv("INGESTFORGE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("INGESTFORGE_OPENAI_MODEL", "test-model")
    monkeypatch.setattr("ingestforge.core.provider_doctor.httpx.post", fake_post)

    result = runner.invoke(
        app,
        [
            "doctor",
            "providers",
            "--offline",
            "--live",
            "--profile",
            "profiles/examples/openai_live.yaml",
        ],
    )
    assert result.exit_code == 0
    assert '"live_smoke": "skipped"' in result.output
    assert calls == []
