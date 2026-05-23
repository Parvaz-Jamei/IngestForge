from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestforge import ingest_url
from ingestforge.core.config import ConfigError, load_profile
from ingestforge.core.contracts import (
    ArticleObject,
    EvidenceBundle,
    MultilingualText,
    SourceRef,
    StandardPackage,
    stable_json_hash,
)
from ingestforge.core.errors import SafeUrlError
from ingestforge.core.validation import reflection_gate
from ingestforge.datasets.chunker import chunk_text
from ingestforge.datasets.writer import DatasetWriter
from ingestforge.observability.provenance import ProvenanceLedger
from ingestforge.providers.fetch.encoding import decode_response_bytes
from ingestforge.providers.fetch.safe_url import validate_public_url


def test_write_dataset_false_creates_no_run_dir(tmp_path: Path, local_server: str):
    profile = load_profile(
        "manual_safe.yaml",
        overrides={
            "fetch": {"deny_private_networks": False, "robots_policy": "ignore_for_manual"},
            "media": {"max_images_per_job": 0},
            "pipeline": {"write_dataset": False},
        },
    )
    package = ingest_url(
        local_server + "/article", profile=profile, runs_dir=tmp_path, write_dataset=False
    )
    assert package.package_hash
    assert list(tmp_path.iterdir()) == []


def test_dataset_package_hash_includes_dataset_records(tmp_path: Path):
    source = SourceRef(url="https://example.com/a", source_hash="src1")
    package = StandardPackage(
        source_refs=[source],
        evidence_bundle=EvidenceBundle(source_refs=[source], selected_snippets=["alpha beta"]),
    )
    package.article = ArticleObject(body=MultilingualText(en="alpha beta gamma " * 100))
    run_dir = DatasetWriter(tmp_path).write_package(package)
    data = json.loads((run_dir / "package.json").read_text())
    stored = data.pop("package_hash")
    recomputed = stable_json_hash(data)
    assert stored == recomputed
    manifest = json.loads((run_dir / "manifests/dataset_manifest.json").read_text())
    assert manifest["package_hash"] == stored


def test_chunker_approximate_tokens_and_legacy_word_args():
    text = "سلام دنیا " * 200
    chunks = chunk_text(
        text, chunk_unit="tokens", tokenizer="approximate", chunk_size=50, chunk_overlap=5
    )
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)
    legacy = chunk_text(" ".join(["word"] * 120), size_words=40, overlap_words=10)
    assert len(legacy) >= 3


def test_config_rejects_ocr_enabled_with_noop_provider():
    with pytest.raises(ConfigError):
        load_profile(
            "manual_safe.yaml", overrides={"media": {"use_ocr": True}, "ocr": {"provider": "noop"}}
        )


def test_strict_allowlist_requires_allowed_domains():
    with pytest.raises(ConfigError):
        load_profile("manual_safe.yaml", overrides={"fetch": {"ssrf_mode": "strict_allowlist"}})


def test_validate_public_url_blocks_ipv4_mapped_ipv6():
    with pytest.raises(SafeUrlError):
        validate_public_url("http://[::ffff:127.0.0.1]/")


def test_decode_windows_1256_persian():
    raw = "سلام دنيا".encode("cp1256")
    decoded = decode_response_bytes(raw, declared_encoding="wrong-charset")
    assert "سلام" in decoded.text
    assert decoded.replacement_count == 0


def test_provenance_has_single_timestamp_key(tmp_path: Path):
    ledger = ProvenanceLedger(tmp_path / "prov.jsonl", config_hash="abc")
    ledger.append(entity="x", activity="fetch_html", agent="test")
    record = json.loads((tmp_path / "prov.jsonl").read_text())
    assert "timestamp" in record
    assert "time" not in record


def test_claim_gate_does_not_mark_unmatched_claim_supported():
    source = SourceRef(url="https://example.com", source_hash="src")
    package = StandardPackage(
        source_refs=[source],
        evidence_bundle=EvidenceBundle(source_refs=[source], clean_text="real evidence text"),
    )
    package.article = ArticleObject(
        description=MultilingualText(en="unmatched generated claim"),
        body=MultilingualText(en="body"),
        title=MultilingualText(en="title"),
    )
    reflection_gate(package)
    assert package.validation_report.claim_records[0].support_status == "needs_review"


def test_claim_gate_exact_snippet_support():
    claim = "Battery connector voltage is present on the measured line."
    source = SourceRef(url="https://example.com", source_hash="src")
    package = StandardPackage(
        source_refs=[source], evidence_bundle=EvidenceBundle(source_refs=[source], clean_text=claim)
    )
    package.article = ArticleObject(
        description=MultilingualText(en=claim),
        body=MultilingualText(en="body"),
        title=MultilingualText(en="title"),
    )
    reflection_gate(package)
    assert package.validation_report.claim_records[0].support_status == "supported_by_exact_quote"
