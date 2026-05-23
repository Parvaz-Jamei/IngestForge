from __future__ import annotations

from ingestforge.datasets.chunker import chunk_text


def test_approximate_chunking_preserves_persian_spacing():
    text = "«سلام» این یک تست است."
    chunks = chunk_text(
        text, chunk_unit="tokens", tokenizer="approximate", chunk_size=3, chunk_overlap=0
    )
    joined = "".join(chunks)
    assert "« سلام »" not in joined
    assert "«سلام»" in joined


def test_approximate_chunking_preserves_arabic_punctuation():
    text = "قال: «مرحبا، يا عالم!»"
    chunks = chunk_text(
        text, chunk_unit="tokens", tokenizer="approximate", chunk_size=5, chunk_overlap=0
    )
    assert "مرحبا،" in "".join(chunks)
    assert "مرحبا ،" not in "".join(chunks)


def test_approximate_chunking_preserves_english_punctuation():
    text = 'He said, "hello." Then left.'
    chunks = chunk_text(
        text, chunk_unit="tokens", tokenizer="approximate", chunk_size=5, chunk_overlap=0
    )
    assert '"hello."' in "".join(chunks)
    assert '" hello . "' not in "".join(chunks)


def test_approximate_chunking_preserves_newlines_inside_chunk():
    text = "alpha\nbeta gamma"
    chunks = chunk_text(
        text, chunk_unit="tokens", tokenizer="approximate", chunk_size=3, chunk_overlap=0
    )
    assert chunks[0] == "alpha\nbeta gamma"


def test_exact_quote_still_exists_after_chunking():
    quote = "Battery connector voltage is present."
    text = f"prefix {quote} suffix"
    chunks = chunk_text(
        text, chunk_unit="tokens", tokenizer="approximate", chunk_size=8, chunk_overlap=0
    )
    assert any(quote in chunk for chunk in chunks)
