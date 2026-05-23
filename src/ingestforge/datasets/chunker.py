from __future__ import annotations

from ingestforge.core.contracts import DatasetRecord, StandardPackage, stable_json_hash
from ingestforge.datasets.tokenizers import tokenizer_for


def chunk_text(
    text: str,
    *,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
    chunk_unit: str = "tokens",
    tokenizer: str = "approximate",
    tokenizer_model: str = "o200k_base",
    size_words: int | None = None,
    overlap_words: int | None = None,
) -> list[str]:
    if size_words is not None:
        chunk_size = size_words
        chunk_unit = "words"
        tokenizer = "words"
    if overlap_words is not None:
        chunk_overlap = overlap_words
    tok = tokenizer_for(chunk_unit=chunk_unit, tokenizer=tokenizer, tokenizer_model=tokenizer_model)
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    step = max(1, chunk_size - chunk_overlap)
    spans = tok.encode_spans(text)
    if spans is not None:
        if not spans:
            return []
        chunks: list[str] = []
        for i in range(0, len(spans), step):
            window = spans[i : i + chunk_size]
            if not window:
                continue
            chunks.append(text[window[0].start : window[-1].end])
        return chunks
    units = tok.encode(text)
    if not units:
        return []
    return [tok.decode(units[i : i + chunk_size]).strip() for i in range(0, len(units), step)]


def build_rag_records(
    package: StandardPackage,
    *,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
    chunk_unit: str = "tokens",
    tokenizer: str = "approximate",
    tokenizer_model: str = "o200k_base",
    chunk_size_tokens: int | None = None,
    chunk_overlap_tokens: int | None = None,
    size_words: int | None = None,
    overlap_words: int | None = None,
) -> list[DatasetRecord]:
    # Backward-compatible parameters for early alpha callers.
    if chunk_size_tokens is not None:
        chunk_size = chunk_size_tokens
    if chunk_overlap_tokens is not None:
        chunk_overlap = chunk_overlap_tokens
    if size_words is not None:
        chunk_size = size_words
        chunk_unit = "words"
        tokenizer = "words"
    if overlap_words is not None:
        chunk_overlap = overlap_words
    records: list[DatasetRecord] = []
    source_ids = [s.source_hash or s.normalized_url or s.url for s in package.source_refs]
    source_url = package.source_refs[0].url if package.source_refs else None
    source_hash = package.source_refs[0].source_hash if package.source_refs else None
    for lang, text in package.article.body.language_map().items():
        for idx, chunk in enumerate(
            chunk_text(
                text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                chunk_unit=chunk_unit,
                tokenizer=tokenizer,
                tokenizer_model=tokenizer_model,
            )
        ):
            rid = stable_json_hash([package.job_id, "generated_article", lang, idx, chunk])
            records.append(
                DatasetRecord(
                    record_id=rid,
                    package_id=package.job_id,
                    record_stage="generated_article",
                    language=lang,
                    text=chunk,
                    source_url=source_url,
                    source_hash=source_hash,
                    source_refs=source_ids,
                    linked_asset_ids=[a.asset_id for a in package.assets],
                    asset_refs=[a.asset_id for a in package.assets],
                    license_status="needs_review",
                    quality_score=package.validation_report.evidence_score,
                )
            )
    for idx, snippet in enumerate(package.evidence_bundle.selected_snippets):
        rid = stable_json_hash([package.job_id, "source_extracted", idx, snippet])
        records.append(
            DatasetRecord(
                record_id=rid,
                package_id=package.job_id,
                record_stage="source_extracted",
                language="mixed",
                text=snippet,
                source_url=source_url,
                source_hash=source_hash,
                source_refs=source_ids,
                license_status="needs_review",
                quality_score=package.validation_report.evidence_score,
            )
        )
    for asset in package.assets:
        if asset.ocr_text:
            rid = stable_json_hash([package.job_id, "ocr_excerpt", asset.asset_id, asset.ocr_text])
            records.append(
                DatasetRecord(
                    record_id=rid,
                    package_id=package.job_id,
                    record_stage="ocr_excerpt",
                    modality="ocr",
                    text=asset.ocr_text,
                    source_url=asset.source_url,
                    source_hash=asset.normalized_url_hash,
                    source_refs=source_ids,
                    asset_refs=[asset.asset_id],
                    linked_asset_ids=[asset.asset_id],
                    license_status=asset.license_status,
                    quality_score=asset.vision_result.get("quality_score", 0.0)
                    if asset.vision_result
                    else 0.0,
                )
            )
        if asset.vision_result:
            rid = stable_json_hash(
                [package.job_id, "image_observation", asset.asset_id, asset.vision_result]
            )
            records.append(
                DatasetRecord(
                    record_id=rid,
                    package_id=package.job_id,
                    record_stage="image_observation",
                    modality="image",
                    text=str(asset.vision_result.get("reason", "")),
                    source_url=asset.source_url,
                    source_hash=asset.normalized_url_hash,
                    source_refs=source_ids,
                    asset_refs=[asset.asset_id],
                    linked_asset_ids=[asset.asset_id],
                    license_status=asset.license_status,
                    quality_score=float(asset.vision_result.get("quality_score", 0.0)),
                )
            )
    return records
