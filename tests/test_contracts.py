from ingestforge.core.contracts import (
    ArticleObject,
    EvidenceBundle,
    MultilingualText,
    SourceRef,
    StandardPackage,
)


def test_evidence_hash_stable():
    e = EvidenceBundle(
        source_refs=[SourceRef(url="https://example.com", normalized_url="https://example.com")],
        selected_snippets=["a"],
    )
    assert e.evidence_hash() == e.evidence_hash()


def test_package_validation_requires_text():
    p = StandardPackage(source_refs=[SourceRef(url="https://example.com")])
    report = p.validate_package()
    assert not report.is_valid


def test_valid_package():
    p = StandardPackage(
        source_refs=[SourceRef(url="https://example.com")],
        article=ArticleObject(title=MultilingualText(en="Title"), body=MultilingualText(en="Body")),
    )
    assert p.validate_package().is_valid
