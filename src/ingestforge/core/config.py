from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from importlib import resources
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ingestforge.core.errors import ConfigError
from ingestforge.core.languages import normalize_source_language, parse_language_list
from ingestforge.core.prompts import resolve_prompt

ENV_PATTERN = re.compile(r"\$\{env:([A-Z0-9_]+)(?::([^}]*))?\}")


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INGESTFORGE_", extra="ignore")

    ai_provider: str | None = None
    ai_model: str | None = None
    openai_api_key: str | None = None
    deepseek_api_key: str | None = None
    gemini_api_key: str | None = None
    openai_model: str | None = None
    deepseek_model: str | None = None
    gemini_model: str | None = None
    target_languages: str | None = None
    source_language: str | None = None
    search_provider: str | None = None
    destination_base_url: str | None = None


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):

        def repl(match: re.Match[str]) -> str:
            key, default = match.group(1), match.group(2)
            return os.getenv(key, default or "")

        return ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in update.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PipelineConfig(StrictModel):
    mode: Literal[
        "manual_url", "dataset_only", "search_to_dataset", "validate_only", "package_only"
    ] = "manual_url"
    dry_run: bool = True
    human_review_required: bool = True
    external_calls: Literal["disabled", "ai_only", "search_only", "enabled", "profile"] = "disabled"
    write_dataset: bool = True
    send_destination: bool = False


class AIThinkingConfig(StrictModel):
    enabled: bool = False


class AIConfig(StrictModel):
    provider: str = "mock"
    model: str = "mock"
    structured_output: bool = True
    strict_structured_output: bool = True
    temperature: float = 0.0
    max_input_chars_per_request: int = Field(default=30000, ge=1000)
    max_output_tokens: int = Field(default=3000, ge=1)
    prompt_version: str = "article_builder.v1"
    source_language: str = "auto"
    target_languages: list[str] = Field(default_factory=lambda: ["en"])
    allow_json_repair: bool = False
    thinking: AIThinkingConfig = Field(default_factory=AIThinkingConfig)
    api_style: Literal["current_response_format", "legacy_response_schema"] = (
        "current_response_format"
    )

    @model_validator(mode="before")
    @classmethod
    def parse_language_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "target_languages" in data:
                data["target_languages"] = parse_language_list(
                    data["target_languages"], field_name="ai.target_languages"
                )
            if "source_language" in data:
                data["source_language"] = normalize_source_language(data["source_language"])
        return data

    @field_validator("provider")
    @classmethod
    def provider_must_be_non_empty(cls, value: str) -> str:
        provider = str(value or "").strip().lower()
        if not provider:
            raise ValueError("ai.provider must not be empty")
        return provider

    @field_validator("target_languages")
    @classmethod
    def target_languages_are_language_tags(cls, value: list[str]) -> list[str]:
        return parse_language_list(value, field_name="ai.target_languages")

    @field_validator("source_language")
    @classmethod
    def source_language_is_auto_or_language_tag(cls, value: str) -> str:
        return normalize_source_language(value)


class SearchConfig(StrictModel):
    provider: str = "manual"
    max_results: int = Field(default=10, ge=1, le=50)
    allowed_domains: list[str] = Field(default_factory=list)
    denied_domains: list[str] = Field(default_factory=list)
    allow_subdomains: bool = True
    obey_robots_txt: bool = True
    timeout_seconds: float = Field(default=15.0, gt=0)
    retry_attempts: int = Field(default=2, ge=0, le=5)

    @field_validator("allowed_domains", "denied_domains")
    @classmethod
    def domain_lists_must_not_contain_empty_values(cls, value: list[str], info: Any) -> list[str]:
        out: list[str] = []
        for item in value:
            normalized = str(item or "").strip().lower().rstrip(".")
            if not normalized:
                raise ValueError(f"search.{info.field_name} must not contain empty domain values")
            out.append(normalized)
        return out


class FetchConfig(StrictModel):
    timeout_seconds: int = Field(default=20, gt=0)
    max_html_bytes: int = Field(default=2_000_000, ge=1024)
    stream_downloads: Literal[True] = True
    deny_private_networks: bool = True
    recheck_after_redirect: Literal[True] = True
    max_redirects: int = Field(default=5, ge=0, le=10)
    user_agent: str = "IngestForge/0.4.0a6"
    require_https: bool = False
    robots_policy: Literal["fail_closed", "fail_open", "ignore_for_manual"] = "fail_closed"
    robots_cache_ttl_seconds: int = Field(default=86400, ge=0)
    max_robots_bytes: int = Field(default=262144, ge=1024)
    ssrf_mode: Literal["validate", "strict_allowlist"] = "validate"


class ExtractionConfig(StrictModel):
    backend: Literal["auto", "internal", "trafilatura"] = "auto"
    trafilatura_favor_precision: bool = False
    trafilatura_favor_recall: bool = False
    include_comments: bool = False
    include_tables: bool = True
    min_extracted_chars: int = Field(default=40, ge=0)

    @model_validator(mode="after")
    def precision_and_recall_are_mutually_exclusive(self) -> ExtractionConfig:
        if self.trafilatura_favor_precision and self.trafilatura_favor_recall:
            raise ValueError(
                "extraction.trafilatura_favor_precision and "
                "extraction.trafilatura_favor_recall cannot both be true"
            )
        return self


class MediaConfig(StrictModel):
    max_images_per_job: int = Field(default=8, ge=0, le=100)
    max_image_bytes: int = Field(default=8_000_000, ge=1024)
    min_width: int = Field(default=32, ge=1)
    min_height: int = Field(default=32, ge=1)
    use_ocr: bool = False
    use_vision_ranker: bool = False


class OCRConfig(StrictModel):
    provider: Literal["noop", "tesseract"] = "noop"
    languages: list[str] = Field(default_factory=lambda: ["eng"])


class VisionConfig(StrictModel):
    provider: Literal["local_heuristic", "openai", "gemini", "local"] = "local_heuristic"
    model: str = "local-heuristic"
    max_images_to_send: int = Field(default=5, ge=0, le=50)
    min_quality_score: float = Field(default=0.6, ge=0.0, le=1.0)


class DatasetConfig(StrictModel):
    write_raw: bool = True
    write_clean: bool = True
    write_chunks: bool = True
    write_manifests: bool = True
    chunk_unit: Literal["tokens", "words", "chars"] = "tokens"
    tokenizer: Literal["approximate", "tiktoken", "words", "chars"] = "approximate"
    tokenizer_model: str = "o200k_base"
    chunk_size: int = Field(default=700, ge=20)
    chunk_overlap: int = Field(default=100, ge=0)
    write_data_card: bool = True

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_chunk_names(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "chunk_size_tokens" in data and "chunk_size" not in data:
                data["chunk_size"] = data.pop("chunk_size_tokens")
            else:
                data.pop("chunk_size_tokens", None)
            if "chunk_overlap_tokens" in data and "chunk_overlap" not in data:
                data["chunk_overlap"] = data.pop("chunk_overlap_tokens")
            else:
                data.pop("chunk_overlap_tokens", None)
        return data

    @field_validator("chunk_overlap")
    @classmethod
    def overlap_is_smaller_than_chunk(cls, value: int, info: Any) -> int:
        chunk = info.data.get("chunk_size", 700)
        if value >= chunk:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return value


class GateConfig(StrictModel):
    min_evidence_score: float = Field(default=0.25, ge=0.0, le=1.0)
    min_source_count: int = Field(default=1, ge=0)
    min_clean_text_chars: int = Field(default=120, ge=0)
    require_source_refs: bool = True
    fail_on_empty_extraction: bool = True
    allow_weak_claims: bool = False


class DestinationAuthConfig(StrictModel):
    mode: Literal[
        "none", "bearer", "bearer_token", "bearer_with_optional_csrf", "bearer_with_csrf"
    ] = "none"
    token_env: str | None = None


class EndpointConfig(StrictModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    path: str
    content_type: Literal["json", "multipart"] = "json"


class RetryConfig(StrictModel):
    attempts: int = Field(default=3, ge=1, le=8)
    backoff_seconds: float = Field(default=2.0, ge=0.0)


class IdempotencyConfig(StrictModel):
    enabled: bool = True
    header: str = "Idempotency-Key"


class DestinationConfig(StrictModel):
    provider: str = "local_export"
    base_url: str | None = None
    auth: DestinationAuthConfig = Field(default_factory=DestinationAuthConfig)
    endpoints: dict[str, EndpointConfig] = Field(default_factory=dict)
    field_map: dict[str, str] = Field(default_factory=dict)
    response_map: dict[str, dict[str, str]] = Field(default_factory=dict)
    payload_templates: dict[str, dict[str, Any]] = Field(default_factory=dict)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    idempotency: IdempotencyConfig = Field(default_factory=IdempotencyConfig)


class IngestForgeProfile(StrictModel):
    profile_name: str = "default"
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    fetch: FetchConfig = Field(default_factory=FetchConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    media: MediaConfig = Field(default_factory=MediaConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    dataset: DatasetConfig = Field(default_factory=DatasetConfig)
    gates: GateConfig = Field(default_factory=GateConfig)
    destination: DestinationConfig = Field(default_factory=DestinationConfig)

    @model_validator(mode="after")
    def validate_cross_field_consistency(self) -> IngestForgeProfile:
        if self.media.use_ocr and self.ocr.provider == "noop":
            raise ValueError("media.use_ocr=true requires a real OCR provider such as 'tesseract'")
        if self.fetch.ssrf_mode == "strict_allowlist" and not self.search.allowed_domains:
            raise ValueError("fetch.ssrf_mode=strict_allowlist requires search.allowed_domains")
        live_ai_modes = {"ai_only", "enabled"}
        if (
            self.ai.provider != "mock"
            and self.pipeline.external_calls in live_ai_modes
            and not (self.ai.model or "").strip()
        ):
            provider_env = f"INGESTFORGE_{self.ai.provider.upper()}_MODEL"
            raise ValueError(
                f"ai.model must be set for live provider {self.ai.provider!r}. "
                f"Set it in the profile, {provider_env}, or INGESTFORGE_AI_MODEL."
            )
        resolve_prompt(self.ai.prompt_version)
        if self.pipeline.send_destination and self.pipeline.dry_run:
            raise ValueError(
                "pipeline.send_destination=true cannot be combined with pipeline.dry_run=true"
            )
        return self


def config_sha256(config: IngestForgeProfile) -> str:
    payload = config.model_dump(mode="json")
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


DEFAULTS: dict[str, Any] = IngestForgeProfile().model_dump()


def _env_overrides(prefix: str = "INGESTFORGE__") -> dict[str, Any]:
    root: dict[str, Any] = {}
    # Backward-compatible nested env support: INGESTFORGE__AI__PROVIDER=mock
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix) :].lower().split("__")
        cur: dict[str, Any] = root
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = _parse_env_scalar(value)

    # User-facing flat variables requested in the public docs.
    settings = EnvSettings()
    flat: dict[str, Any] = {}
    if settings.ai_provider:
        flat.setdefault("ai", {})["provider"] = settings.ai_provider
    # INGESTFORGE_AI_MODEL is handled after provider resolution so explicit
    # profile values keep precedence over generic environment defaults.
    if settings.target_languages:
        flat.setdefault("ai", {})["target_languages"] = settings.target_languages
    if settings.source_language:
        flat.setdefault("ai", {})["source_language"] = settings.source_language
    if settings.search_provider:
        flat.setdefault("search", {})["provider"] = settings.search_provider
    dest_url = settings.destination_base_url or os.getenv("DESTINATION_BASE_URL")
    if dest_url:
        flat.setdefault("destination", {})["base_url"] = dest_url
    return _deep_merge(root, flat)


def _parse_env_scalar(value: str) -> Any:
    low = value.lower()
    if low in {"true", "false"}:
        return low == "true"
    try:
        return int(value)
    except ValueError:
        return value


def _read_profile_text(path: str | Path) -> str:
    candidate = Path(path)
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    try:
        profile_root = resources.files("ingestforge.profiles")
        parts = candidate.parts
        if "profiles" in parts:
            parts = parts[parts.index("profiles") + 1 :]
        if not parts:
            parts = (candidate.name,)
        packaged = profile_root.joinpath(*parts)
        if packaged.is_file():
            return packaged.read_text(encoding="utf-8")
        return (profile_root / candidate.name).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, AttributeError) as exc:
        raise ConfigError(f"profile not found: {path}") from exc


def _load_profile_dict(path: str | Path, *, seen: set[str] | None = None) -> dict[str, Any]:
    seen = seen or set()
    key = str(path)
    if key in seen:
        raise ConfigError(f"circular profile inheritance detected: {path}")
    seen.add(key)
    raw = yaml.safe_load(_read_profile_text(path)) or {}
    raw = _expand_env(raw)
    parent = raw.get("extends")
    if parent:
        base_path = Path(path).parent / str(parent) if Path(path).parent else Path(str(parent))
        base = _load_profile_dict(base_path, seen=seen)
        return _deep_merge(base, raw)
    return raw


def _apply_provider_model_policy(data: dict[str, Any]) -> dict[str, Any]:
    resolved = deepcopy(data)
    ai = resolved.setdefault("ai", {})
    raw_provider = ai.get("provider", "mock")
    provider = str(raw_provider).strip().lower() if raw_provider is not None else "mock"
    # Do not silently turn an explicitly empty provider into mock. This catches
    # live templates where ${env:INGESTFORGE_AI_PROVIDER} was not set.
    if not provider:
        ai["provider"] = ""
        return resolved
    ai["provider"] = provider
    model = str(ai.get("model") or "").strip()
    if provider == "mock":
        if not model:
            ai["model"] = "mock"
        return resolved

    # Treat the library's offline placeholder as unresolved when a live provider is selected
    # through an environment override. Model IDs remain opaque; only emptiness is checked.
    if not model or model in {"mock", "local-mock"}:
        provider_env = f"INGESTFORGE_{provider.upper()}_MODEL"
        model = (os.getenv(provider_env) or os.getenv("INGESTFORGE_AI_MODEL") or "").strip()
        ai["model"] = model
    return resolved


def load_profile(
    path: str | Path | None = None, overrides: dict[str, Any] | None = None
) -> IngestForgeProfile:
    data = dict(DEFAULTS)
    if path:
        data = _deep_merge(data, _load_profile_dict(path))
    data = _deep_merge(data, _env_overrides())
    if overrides:
        data = _deep_merge(data, overrides)
    data = _apply_provider_model_policy(data)
    try:
        return IngestForgeProfile.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc


def validate_profile(path: str | Path) -> IngestForgeProfile:
    return load_profile(path)


def write_resolved_profile(profile: IngestForgeProfile, run_dir: str | Path) -> Path:
    path = Path(run_dir) / "resolved_profile.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return path
