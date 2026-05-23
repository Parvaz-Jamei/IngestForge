from __future__ import annotations

import os
from typing import Any

import httpx

import ingestforge.providers.ai  # noqa: F401
from ingestforge.core.config import IngestForgeProfile
from ingestforge.core.contracts import EvidenceBundle
from ingestforge.core.errors import ConfigError
from ingestforge.core.registry import registry

_DOCTOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "summary": {"type": "string"}},
    "required": ["ok", "summary"],
}


def _provider_api_style(profile: IngestForgeProfile) -> str:
    if profile.ai.provider == "openai":
        return "responses_api_json_schema"
    if profile.ai.provider == "deepseek":
        return "openai_compatible_json_object_with_thinking"
    if profile.ai.provider == "gemini":
        return profile.ai.api_style
    return "mock"


def _validate_payload_contract(provider: str, payload: dict[str, Any] | None) -> list[str]:
    errors: list[str] = []
    if provider == "mock":
        return errors
    if not payload:
        return ["provider did not build a payload"]
    if payload.get("model") in {None, ""}:
        errors.append("payload.model is empty")
    if provider == "openai":
        fmt = payload.get("text", {}).get("format", {})
        if fmt.get("type") != "json_schema" or fmt.get("strict") is not True:
            errors.append("OpenAI payload must use text.format.type=json_schema with strict=true")
        if payload.get("store") is not False:
            errors.append("OpenAI payload must set store=false")
    elif provider == "deepseek":
        if payload.get("response_format") != {"type": "json_object"}:
            errors.append("DeepSeek payload must use response_format.type=json_object")
        if payload.get("thinking", {}).get("type") not in {"enabled", "disabled"}:
            errors.append("DeepSeek payload must include thinking.type enabled|disabled")
    elif provider == "gemini":
        generation_config = payload.get("generationConfig", {})
        response_format = generation_config.get("responseFormat", {})
        legacy_mime = generation_config.get("responseMimeType")
        if response_format:
            text = response_format.get("text", {})
            if text.get("mimeType") != "application/json" or "schema" not in text:
                errors.append(
                    "Gemini current payload must use generationConfig.responseFormat.text.mimeType/schema"
                )
        elif legacy_mime != "application/json" or "responseSchema" not in generation_config:
            errors.append(
                "Gemini payload must use current responseFormat or explicit legacy responseSchema"
            )
    else:
        errors.append(f"unknown provider: {provider}")
    return errors


def _extract_live_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:500]
    if isinstance(body, dict) and "error" in body:
        return str(body["error"])
    return str(body)[:500]


def _run_live_smoke(provider_id: str, model: str, payload: dict[str, Any]) -> tuple[str, list[str]]:
    """Run an explicitly opted-in minimal provider request.

    This is intentionally limited to the doctor command and uses direct HTTP requests
    so the core alpha package does not require provider SDKs at runtime. The caller
    already checked `INGESTFORGE_RUN_LIVE_PROVIDER_TESTS=1` and provider key presence.
    """
    warnings: list[str] = []
    timeout = httpx.Timeout(30.0, connect=10.0)
    try:
        if provider_id == "openai":
            api_key = os.environ["INGESTFORGE_OPENAI_API_KEY"]
            base_url = os.getenv("INGESTFORGE_OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip(
                "/"
            )
            response = httpx.post(
                f"{base_url}/responses",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
        elif provider_id == "deepseek":
            api_key = os.environ["INGESTFORGE_DEEPSEEK_API_KEY"]
            base_url = os.getenv(
                "INGESTFORGE_DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            ).rstrip("/")
            response = httpx.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
        elif provider_id == "gemini":
            api_key = os.environ["INGESTFORGE_GEMINI_API_KEY"]
            base_url = os.getenv(
                "INGESTFORGE_GEMINI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta",
            ).rstrip("/")
            model_path = model if model.startswith("models/") else f"models/{model}"
            gemini_payload = dict(payload)
            gemini_payload.pop("model", None)
            response = httpx.post(
                f"{base_url}/{model_path}:generateContent",
                headers={"Content-Type": "application/json"},
                params={"key": api_key},
                json=gemini_payload,
                timeout=timeout,
            )
        else:
            return "skipped", [f"no live smoke implementation for provider {provider_id!r}"]
    except httpx.HTTPError as exc:
        return "fail", [f"live smoke transport error: {type(exc).__name__}: {exc}"]

    if 200 <= response.status_code < 300:
        try:
            response.json()
        except ValueError:
            warnings.append("live smoke returned HTTP success but non-JSON response")
            return "fail", warnings
        return "pass", warnings
    warnings.append(f"live smoke HTTP {response.status_code}: {_extract_live_error(response)}")
    return "fail", warnings


def run_provider_doctor(profile: IngestForgeProfile, *, live: bool = False) -> dict[str, Any]:
    provider_id = profile.ai.provider
    warnings: list[str] = []
    payload: dict[str, Any] | None = None
    try:
        if provider_id == "mock":
            local_schema_validation = "pass"
            payload_contract = "pass"
        else:
            cls = registry.get_ai(provider_id)
            provider = cls(
                model=profile.ai.model,
                temperature=profile.ai.temperature,
                max_output_tokens=profile.ai.max_output_tokens,
                max_input_chars=profile.ai.max_input_chars_per_request,
                thinking_enabled=profile.ai.thinking.enabled,
                api_style=profile.ai.api_style,
            )
            evidence = EvidenceBundle(clean_text="Provider doctor local contract smoke.")
            payload = provider.build_payload(evidence, _DOCTOR_SCHEMA)
            contract_errors = _validate_payload_contract(provider_id, payload)
            payload_contract = "fail" if contract_errors else "pass"
            local_schema_validation = "fail" if contract_errors else "pass"
            warnings.extend(contract_errors)
    except Exception as exc:
        payload_contract = "fail"
        local_schema_validation = "fail"
        warnings.append(f"{type(exc).__name__}: {exc}")

    live_smoke = "skipped"
    if live:
        run_live = os.getenv("INGESTFORGE_RUN_LIVE_PROVIDER_TESTS") == "1"
        key_env = f"INGESTFORGE_{provider_id.upper()}_API_KEY"
        model_env = f"INGESTFORGE_{provider_id.upper()}_MODEL"
        if provider_id == "mock":
            live_smoke = "skipped"
            warnings.append("mock provider has no live smoke test")
        elif not run_live:
            warnings.append(
                "live smoke skipped; set INGESTFORGE_RUN_LIVE_PROVIDER_TESTS=1 to opt in"
            )
        elif not os.getenv(key_env) or not (profile.ai.model or os.getenv(model_env)):
            warnings.append(f"live smoke skipped; missing {key_env} or {model_env}")
        elif payload_contract != "pass" or payload is None:
            live_smoke = "fail"
            warnings.append("live smoke not run because local payload contract failed")
        else:
            live_smoke, live_warnings = _run_live_smoke(provider_id, profile.ai.model, payload)
            warnings.extend(live_warnings)

    result = {
        "provider": provider_id,
        "model": profile.ai.model,
        "api_style": _provider_api_style(profile),
        "external_calls": profile.pipeline.external_calls,
        "payload_contract": payload_contract,
        "local_schema_validation": local_schema_validation,
        "live_smoke": live_smoke,
        "warnings": warnings,
    }
    if result["payload_contract"] == "fail":
        raise ConfigError(str(result))
    return result
