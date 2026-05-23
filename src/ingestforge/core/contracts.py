from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def stable_json_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class ProviderCapabilities:
    structured_output: Literal[
        "none", "json_object", "json_schema_strict", "json_schema_subset"
    ] = "none"
    supports_vision: bool = False
    supports_ocr: bool = False
    supports_thinking_control: bool = False
    supports_tools: bool = False
    live_calls_enabled: bool = False
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None

    # Backward-friendly aliases for older internal tests/users.
    @property
    def supports_strict_json_schema(self) -> bool:
        return self.structured_output == "json_schema_strict"

    @property
    def supports_json_mode(self) -> bool:
        return self.structured_output in {"json_object", "json_schema_strict", "json_schema_subset"}

    @property
    def supports_tool_calling(self) -> bool:
        return self.supports_tools


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    normalized_url: str | None = None
    source_hash: str | None = None
    source_domain: str | None = None
    title: str | None = None
    license_status: str = "needs_review"
    robots_allowed: bool | None = None
    extraction_method: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    source_quality_score: float = 0.0
    extraction_quality_score: float = 0.0
    source_risk_flags: list[str] = Field(default_factory=list)

    @field_validator("license_status")
    @classmethod
    def license_is_known(cls, value: str) -> str:
        allowed = {"unknown", "needs_review", "allowed", "own_content", "rejected", "restricted"}
        if value not in allowed:
            raise ValueError(f"invalid license_status: {value}")
        return value


class AssetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(default_factory=lambda: f"asset_{uuid4().hex[:12]}")
    source_url: str | None = None
    normalized_url_hash: str | None = None
    local_path: str | None = None
    export_path: str | None = None
    sha256: str | None = None
    content_hash_prefix: str | None = None
    perceptual_hash: str | None = None
    modality: Literal["image", "document", "audio", "video", "other"] = "image"
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    ocr_text: str | None = None
    ocr_confidence: float | None = None
    ocr_status: str | None = None
    vision_result: dict[str, Any] | None = None
    caption: str | None = None
    license_status: str = "needs_review"
    risk_flags: list[str] = Field(default_factory=list)
    source_quality_score: float = 0.0
    extraction_quality_score: float = 0.0
    source_risk_flags: list[str] = Field(default_factory=list)


class MultilingualText(BaseModel):
    """Text keyed by language tag.

    `fa` and `en` stay as first-class backward-compatible fields, while
    additional BCP 47-style language tags such as `de`, `ar`, `pt-BR`,
    `zh-Hant`, or private-use tags are accepted through model extras.
    """

    model_config = ConfigDict(extra="allow")
    fa: str = ""
    en: str = ""

    @model_validator(mode="after")
    def validate_dynamic_language_fields(self) -> MultilingualText:
        from ingestforge.core.languages import normalize_language_tag

        for key, value in (self.model_extra or {}).items():
            normalize_language_tag(key, field_name="MultilingualText language key")
            if not isinstance(value, str):
                raise ValueError(f"MultilingualText value for {key!r} must be a string")
        return self

    @classmethod
    def from_languages(cls, languages: list[str], text: str) -> MultilingualText:
        return cls.model_validate({language: text for language in languages})

    def language_map(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if self.fa:
            values["fa"] = self.fa
        if self.en:
            values["en"] = self.en
        for key, value in (self.model_extra or {}).items():
            if isinstance(value, str) and value:
                values[str(key)] = value
        return values

    def first_text(self) -> str:
        for value in self.language_map().values():
            if value.strip():
                return value
        return ""


class ArticleObject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: MultilingualText = Field(default_factory=MultilingualText)
    description: MultilingualText = Field(default_factory=MultilingualText)
    body: MultilingualText = Field(default_factory=MultilingualText)
    tags: list[str] = Field(default_factory=list)
    tags_text: str = ""
    seo: dict[str, Any] = Field(default_factory=dict)
    domain_meta: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_title: str | None = None
    source_refs: list[SourceRef] = Field(default_factory=list)
    clean_text: str = ""
    selected_snippets: list[str] = Field(default_factory=list)
    ocr_excerpts: list[str] = Field(default_factory=list)
    selected_image_observations: list[dict[str, Any]] = Field(default_factory=list)
    detected_entities: dict[str, Any] = Field(default_factory=dict)
    source_risk_flags: list[str] = Field(default_factory=list)
    prompt_version: str = "article_builder.v1"
    provider_id: str = "mock"
    model_id: str = "mock"

    def compact(self, max_chars: int = 30000) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        remaining = max_chars
        clean_text = str(payload.get("clean_text") or "")
        if len(clean_text) > remaining:
            payload["clean_text"] = clean_text[:remaining]
            payload.setdefault("source_risk_flags", []).append("clean_text_truncated")
        remaining = max(0, max_chars - len(str(payload.get("clean_text") or "")))
        snippets: list[str] = []
        for snippet in payload.get("selected_snippets") or []:
            if remaining <= 0:
                break
            text = str(snippet)
            snippets.append(text[:remaining])
            remaining -= len(snippets[-1])
        payload["selected_snippets"] = snippets
        return payload

    def evidence_hash(self) -> str:
        core = {
            "urls": [s.normalized_url or s.url for s in self.source_refs],
            "snippets": self.selected_snippets,
            "assets": [
                i.get("sha256") or i.get("asset_id") for i in self.selected_image_observations
            ],
            "prompt_version": self.prompt_version,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
        }
        return stable_json_hash(core)


class ClaimRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str = Field(default_factory=lambda: f"claim_{uuid4().hex[:12]}")
    claim_text: str
    supporting_source_refs: list[str] = Field(default_factory=list)
    supporting_dataset_record_ids: list[str] = Field(default_factory=list)
    supporting_source_hashes: list[str] = Field(default_factory=list)
    supporting_asset_ids: list[str] = Field(default_factory=list)
    support_status: Literal[
        "not_checked", "weak", "needs_review", "supported_by_exact_quote", "unsupported"
    ] = "needs_review"
    notes: str | None = None


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_valid: bool = True
    schema_valid: bool = True
    evidence_score: float = 0.0
    coverage_score: float = 0.0
    source_diversity_score: float = 0.0
    image_relevance_score: float = 0.0
    ocr_quality_score: float = 0.0
    risk_level: Literal["low", "medium", "high"] = "medium"
    can_generate: bool = True
    human_review_required: bool = True
    evidence_gate: dict[str, Any] = Field(default_factory=dict)
    claim_gate: dict[str, Any] = Field(default_factory=dict)
    media_gate: dict[str, Any] = Field(default_factory=dict)
    license_gate: dict[str, Any] = Field(default_factory=dict)
    destination_gate: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    reflection: dict[str, Any] = Field(default_factory=dict)
    claim_records: list[ClaimRecord] = Field(default_factory=list)


class DestinationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = "local_export"
    dry_run: bool = True
    status: str = "review"
    indexing: str = "disabled"
    human_review_required: bool = True
    field_map: dict[str, str] = Field(default_factory=dict)


class DatasetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str
    package_id: str | None = None
    record_stage: Literal[
        "source_extracted", "generated_article", "ocr_excerpt", "image_observation"
    ] = "generated_article"
    modality: str = "text"
    language: str = "mixed"
    text: str = ""
    source_url: str | None = None
    source_hash: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    asset_refs: list[str] = Field(default_factory=list)
    linked_asset_ids: list[str] = Field(default_factory=list)
    provenance_ids: list[str] = Field(default_factory=list)
    license_status: str = "needs_review"
    quality_score: float = 0.0
    created_at: datetime = Field(default_factory=utc_now)


class StandardPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "ingestforge.package.v1"
    job_id: str = Field(default_factory=lambda: f"job_{uuid4().hex[:16]}")
    created_at: datetime = Field(default_factory=utc_now)
    article: ArticleObject = Field(default_factory=ArticleObject)
    assets: list[AssetRecord] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    evidence_bundle: EvidenceBundle = Field(default_factory=EvidenceBundle)
    validation_report: ValidationReport = Field(default_factory=ValidationReport)
    provenance: dict[str, Any] = Field(default_factory=dict)
    dataset_records: list[DatasetRecord] = Field(default_factory=list)
    destination_plan: DestinationPlan = Field(default_factory=DestinationPlan)
    evidence_bundle_hash: str | None = None
    package_hash: str | None = None

    def finalize_hashes(self) -> None:
        self.evidence_bundle_hash = self.evidence_bundle.evidence_hash()
        payload = self.model_dump(mode="json", exclude={"package_hash"})
        self.package_hash = stable_json_hash(payload)

    def validate_package(self) -> ValidationReport:
        report = ValidationReport(is_valid=True, schema_valid=True, human_review_required=True)
        if not self.source_refs:
            report.warnings.append("package_has_no_source_refs")
            report.license_gate["source_refs_present"] = False
        if not self.article.title.first_text():
            report.errors.append("article_title_missing")
        if not (self.article.body.first_text() or self.article.description.first_text()):
            report.errors.append("article_text_missing")
        if any(s.license_status not in {"allowed", "own_content"} for s in self.source_refs):
            report.warnings.append("some_sources_need_license_review")
            report.license_gate["needs_review"] = True
        report.is_valid = not report.errors
        report.can_generate = report.is_valid
        self.validation_report = report
        return report

    def write_dataset(self, runs_dir: str | Path = "runs", *, config: Any | None = None) -> Path:
        from ingestforge.datasets.writer import DatasetWriter

        writer = DatasetWriter(Path(runs_dir), config=config)
        return writer.write_package(self)
