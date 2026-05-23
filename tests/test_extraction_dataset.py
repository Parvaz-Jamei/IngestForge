from ingestforge.core.contracts import ArticleObject, MultilingualText, SourceRef, StandardPackage
from ingestforge.datasets.chunker import build_rag_records, chunk_text
from ingestforge.providers.fetch.html_extractor import HtmlExtractor


def test_html_extractor():
    ex = HtmlExtractor().extract(
        "<html><title>T</title><body><p>This is a paragraph with enough length to be selected by the extractor.</p></body></html>"
    )
    assert ex.title == "T" and ex.snippets


def test_chunk_text():
    chunks = chunk_text(" ".join(["word"] * 150), size_words=50, overlap_words=10)
    assert len(chunks) >= 3


def test_rag_records_preserve_source():
    p = StandardPackage(
        source_refs=[SourceRef(url="https://example.com", source_hash="abc")],
        article=ArticleObject(
            title=MultilingualText(en="T"), body=MultilingualText(en=" ".join(["body"] * 120))
        ),
    )
    recs = build_rag_records(p, size_words=50, overlap_words=0)
    assert recs and recs[0].source_url == "https://example.com"


def test_html_extractor_auto_uses_trafilatura_when_available(monkeypatch):
    import ingestforge.providers.fetch.html_extractor as html_extractor
    from ingestforge.core.config import ExtractionConfig

    def fake_trafilatura_extract(html, *, url, config):
        assert url == "https://example.com/article"
        assert config.include_tables is True
        return "Main article paragraph from Trafilatura.\nSecond extracted paragraph with enough length."

    monkeypatch.setattr(html_extractor, "_trafilatura_extract", fake_trafilatura_extract)
    ex = HtmlExtractor(ExtractionConfig(backend="auto")).extract(
        "<html><title>Article</title><body><nav>Noise</nav><article>ignored fallback</article></body></html>",
        url="https://example.com/article",
    )
    assert ex.clean_text.startswith("Main article paragraph")
    assert ex.diagnostics["backend"] == "trafilatura"
    assert ex.diagnostics["fallback_used"] is False


def test_html_extractor_auto_falls_back_to_internal_when_trafilatura_empty(monkeypatch):
    import ingestforge.providers.fetch.html_extractor as html_extractor
    from ingestforge.core.config import ExtractionConfig

    monkeypatch.setattr(html_extractor, "_trafilatura_extract", lambda *args, **kwargs: None)
    ex = HtmlExtractor(ExtractionConfig(backend="auto")).extract(
        "<html><title>T</title><body><p>This fallback paragraph has enough length to be selected cleanly.</p></body></html>"
    )
    assert ex.diagnostics["backend"] == "internal_bs4"
    assert ex.diagnostics["fallback_used"] is True
    assert "fallback paragraph" in ex.clean_text


def test_html_extractor_trafilatura_backend_does_not_fallback_when_unavailable(monkeypatch):
    import ingestforge.providers.fetch.html_extractor as html_extractor
    from ingestforge.core.config import ExtractionConfig

    monkeypatch.setattr(html_extractor, "_trafilatura_extract", lambda *args, **kwargs: None)
    ex = HtmlExtractor(ExtractionConfig(backend="trafilatura")).extract(
        "<html><title>T</title><body><p>This fallback paragraph has enough length to be selected cleanly.</p></body></html>"
    )
    assert ex.clean_text == ""
    assert ex.diagnostics["backend"] == "trafilatura"
    assert ex.diagnostics["error"] == "trafilatura_unavailable_or_empty"


def test_extraction_config_rejects_precision_and_recall_together():
    from pytest import raises

    from ingestforge.core.config import ExtractionConfig

    with raises(ValueError, match="cannot both be true"):
        ExtractionConfig(trafilatura_favor_precision=True, trafilatura_favor_recall=True)
