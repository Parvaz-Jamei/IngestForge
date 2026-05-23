from __future__ import annotations

import re
from typing import Literal

from ingestforge.core.config import GateConfig
from ingestforge.core.contracts import (
    ClaimRecord,
    EvidenceBundle,
    StandardPackage,
    ValidationReport,
)


def corrective_retrieval_gate(
    evidence: EvidenceBundle, config: GateConfig | None = None, min_score: float | None = None
) -> ValidationReport:
    cfg = config or GateConfig()
    threshold = cfg.min_evidence_score if min_score is None else min_score
    source_score = min(len(evidence.source_refs) / max(cfg.min_source_count, 1), 1.0)
    snippet_score = min(len(evidence.selected_snippets) / 5, 1.0)
    image_score = min(len(evidence.selected_image_observations) / 3, 1.0)
    coverage = min((len(evidence.clean_text) / max(cfg.min_clean_text_chars, 1)), 1.0)
    score = round(
        (source_score * 0.3) + (snippet_score * 0.25) + (coverage * 0.35) + (image_score * 0.1),
        4,
    )
    warnings: list[str] = []
    errors: list[str] = []
    if cfg.require_source_refs and not evidence.source_refs:
        errors.append("source_refs_required")
    if cfg.fail_on_empty_extraction and not evidence.clean_text.strip():
        errors.append("clean_text_required")
    if source_score == 0:
        warnings.append("no_source_refs")
    if coverage < 0.2:
        warnings.append("low_text_coverage")
    if score < threshold:
        errors.append("evidence_score_below_threshold")
    return ValidationReport(
        is_valid=not errors,
        evidence_score=score,
        coverage_score=coverage,
        source_diversity_score=source_score,
        image_relevance_score=image_score,
        ocr_quality_score=min(len(evidence.ocr_excerpts) / 3, 1.0),
        risk_level="high" if score < threshold else "medium",
        can_generate=not errors,
        evidence_gate={
            "min_evidence_score": threshold,
            "min_source_count": cfg.min_source_count,
            "min_clean_text_chars": cfg.min_clean_text_chars,
            "source_count": len(evidence.source_refs),
            "clean_text_chars": len(evidence.clean_text),
            "snippet_count": len(evidence.selected_snippets),
            "image_count": len(evidence.selected_image_observations),
            "ocr_excerpt_count": len(evidence.ocr_excerpts),
            "can_generate": not errors,
        },
        warnings=warnings,
        errors=errors,
    )


def _normalize_claim(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _exact_support(claim: str, evidence_texts: list[str]) -> bool:
    claim_norm = _normalize_claim(claim)
    if len(claim_norm) < 16:
        return False
    return any(claim_norm in _normalize_claim(text) for text in evidence_texts)


def reflection_gate(
    package: StandardPackage, *, allow_weak_claims: bool = False
) -> ValidationReport:
    package.validate_package()
    claim_text = package.article.description.first_text().strip()[:240]
    if not claim_text:
        claim_text = "generated article requires human review"
    evidence_texts = [
        package.evidence_bundle.clean_text,
        *package.evidence_bundle.selected_snippets,
    ]
    supported = _exact_support(claim_text, evidence_texts)
    support_status: Literal["supported_by_exact_quote", "needs_review"] = (
        "supported_by_exact_quote" if supported else "needs_review"
    )
    claim = ClaimRecord(
        claim_text=claim_text,
        supporting_source_refs=[s.source_hash or s.url for s in package.source_refs],
        supporting_source_hashes=[s.source_hash for s in package.source_refs if s.source_hash],
        supporting_asset_ids=[a.asset_id for a in package.assets],
        support_status=support_status,
        notes=(
            "Deterministic alpha claim gate: exact evidence match only. "
            "Semantic support remains a human-review concern."
        ),
    )
    package.validation_report.claim_records = [claim]
    unsupported_count = 0 if supported else 1
    if unsupported_count and not allow_weak_claims:
        package.validation_report.destination_gate["publish_blocked_by_claim_gate"] = True
    package.validation_report.claim_gate = {
        "claim_count": 1,
        "supported_by_exact_quote_count": 1 if supported else 0,
        "needs_review_count": unsupported_count,
        "allow_weak_claims": allow_weak_claims,
    }
    package.validation_report.reflection = {
        "needs_more_retrieval": package.validation_report.evidence_score < 0.45,
        "grounded_in_evidence": supported,
        "citations_sufficient": bool(package.source_refs),
        "images_relevant": any(a.vision_result for a in package.assets) or not package.assets,
        "unsupported_claims_possible": True,
    }
    return package.validation_report
