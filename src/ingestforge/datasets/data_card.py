from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from ingestforge.core.contracts import StandardPackage


def build_dataset_card(package: StandardPackage) -> dict:
    domains = sorted({urlparse(s.url).hostname or "unknown" for s in package.source_refs})
    license_counts: dict[str, int] = {}
    robots_counts: dict[str, int] = {}
    for source in package.source_refs:
        license_counts[source.license_status] = license_counts.get(source.license_status, 0) + 1
        robots_key = str(source.robots_allowed)
        robots_counts[robots_key] = robots_counts.get(robots_key, 0) + 1
    return {
        "package_id": package.job_id,
        "package_hash": package.package_hash,
        "purpose": "AI-ready ingestion package and RAG dataset export",
        "source_types": sorted(
            {
                "web" if s.url.startswith(("http://", "https://")) else "other"
                for s in package.source_refs
            }
        ),
        "source_domains": domains,
        "source_count": len(package.source_refs),
        "license_status_counts": license_counts,
        "license_review_status": "needs_review"
        if license_counts.get("needs_review")
        else "reviewed",
        "robots_status_counts": robots_counts,
        "collection_method": "config-driven ingestion pipeline",
        "extraction_methods": sorted(
            {s.extraction_method or "unknown" for s in package.source_refs}
        ),
        "ocr_enabled": any(a.ocr_status not in {None, "disabled"} for a in package.assets),
        "vision_enabled": any(a.vision_result for a in package.assets),
        "ai_providers_models_used": sorted(
            {f"{package.evidence_bundle.provider_id}:{package.evidence_bundle.model_id}"}
        ),
        "known_limitations": [
            "alpha software; generated content requires human review",
            "robots rules are not copyright permission",
            "local heuristic evaluation is not a legal or technical guarantee",
        ],
        "language_coverage": sorted(package.article.body.language_map().keys()),
        "modalities": sorted({"text", *[a.modality for a in package.assets]}),
        "pii_sensitive_data_notes": "No PII detection guarantee; review before publication.",
        "deduplication_method": "URL hash, asset hash, and package evidence hash",
        "provenance_availability": bool(package.provenance),
        "recommended_uses": ["audit", "RAG retrieval", "human-reviewed content preparation"],
        "unsafe_uses": ["automatic publication without review", "legal reuse determination"],
    }


def write_data_card(package: StandardPackage, run_dir: Path) -> None:
    card = build_dataset_card(package)
    (run_dir / "dataset_card.json").write_text(
        json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md = ["# Dataset Card", ""]
    for key, value in card.items():
        md.append(f"## {key.replace('_', ' ').title()}")
        md.append(
            json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value
        )
        md.append("")
    (run_dir / "DATA_CARD.md").write_text("\n".join(md), encoding="utf-8")
