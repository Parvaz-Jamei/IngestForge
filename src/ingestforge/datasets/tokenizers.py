from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ingestforge.core.errors import OptionalDependencyError, ValidationFailure


@dataclass(frozen=True)
class TokenSpan:
    value: Any
    start: int
    end: int


class BaseTokenizer:
    name: str

    def encode(self, text: str) -> list[Any]:
        raise NotImplementedError

    def decode(self, tokens: list[Any]) -> str:
        raise NotImplementedError

    def encode_spans(self, text: str) -> list[TokenSpan] | None:
        return None


@dataclass(frozen=True)
class WhitespaceTokenizer(BaseTokenizer):
    name: str = "words"

    def encode(self, text: str) -> list[str]:
        return [span.value for span in self.encode_spans(text) or []]

    def encode_spans(self, text: str) -> list[TokenSpan]:
        spans: list[TokenSpan] = []
        in_token = False
        start = 0
        for index, ch in enumerate(text):
            if ch.isspace():
                if in_token:
                    spans.append(TokenSpan(text[start:index], start, index))
                    in_token = False
            elif not in_token:
                start = index
                in_token = True
        if in_token:
            spans.append(TokenSpan(text[start : len(text)], start, len(text)))
        return spans

    def decode(self, tokens: list[Any]) -> str:
        return " ".join(str(t) for t in tokens)


@dataclass(frozen=True)
class CharacterBudgetTokenizer(BaseTokenizer):
    name: str = "chars"

    def encode(self, text: str) -> list[str]:
        return list(text)

    def encode_spans(self, text: str) -> list[TokenSpan]:
        return [TokenSpan(ch, i, i + 1) for i, ch in enumerate(text)]

    def decode(self, tokens: list[Any]) -> str:
        return "".join(str(t) for t in tokens)


@dataclass(frozen=True)
class ApproximateTokenTokenizer(BaseTokenizer):
    """Deterministic span-preserving approximate tokenizer for alpha profiles."""

    name: str = "approximate"

    def encode(self, text: str) -> list[str]:
        return [span.value for span in self.encode_spans(text)]

    def encode_spans(self, text: str) -> list[TokenSpan]:
        out: list[TokenSpan] = []
        current: list[str] = []
        start: int | None = None

        def flush(end: int) -> None:
            nonlocal current, start
            if current and start is not None:
                out.append(TokenSpan("".join(current), start, end))
            current = []
            start = None

        for index, ch in enumerate(text):
            if ch.isspace():
                flush(index)
            elif ch.isalnum() or ch in {"_", "-"}:
                if start is None:
                    start = index
                current.append(ch)
                if len(current) >= 8:
                    flush(index + 1)
            else:
                flush(index)
                out.append(TokenSpan(ch, index, index + 1))
        flush(len(text))
        return out

    def decode(self, tokens: list[Any]) -> str:
        # Kept for compatibility with callers that only hold token values. The chunker uses
        # encode_spans() for this tokenizer so multilingual source text is not reconstructed
        # with artificial spaces.
        return "".join(str(t) for t in tokens)


class TiktokenTokenizer(BaseTokenizer):
    name = "tiktoken"

    def __init__(self, model: str = "o200k_base") -> None:
        try:
            import tiktoken  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - environment dependent
            raise OptionalDependencyError(
                "dataset.tokenizer='tiktoken' requires installing ingestforge[tokenizers]"
            ) from exc
        try:
            self._enc = tiktoken.get_encoding(model)
        except Exception:
            self._enc = tiktoken.get_encoding("o200k_base")

    def encode(self, text: str) -> list[int]:
        return list(self._enc.encode(text))

    def decode(self, tokens: list[Any]) -> str:
        return self._enc.decode([int(t) for t in tokens])


def tokenizer_for(
    *, chunk_unit: str, tokenizer: str, tokenizer_model: str = "o200k_base"
) -> BaseTokenizer:
    if chunk_unit == "words" or tokenizer == "words":
        return WhitespaceTokenizer()
    if chunk_unit == "chars" or tokenizer == "chars":
        return CharacterBudgetTokenizer()
    if chunk_unit == "tokens":
        if tokenizer == "approximate":
            return ApproximateTokenTokenizer()
        if tokenizer == "tiktoken":
            return TiktokenTokenizer(tokenizer_model)
    raise ValidationFailure(
        "invalid dataset tokenizer config; use chunk_unit=tokens with tokenizer=approximate|tiktoken, "
        "or chunk_unit=words/chars"
    )
