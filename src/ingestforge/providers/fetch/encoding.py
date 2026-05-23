from __future__ import annotations

import codecs
import re
from dataclasses import dataclass

CHARSET_RE = re.compile(r"charset=([^;]+)", re.I)


@dataclass(frozen=True)
class DecodeResult:
    text: str
    encoding_used: str
    replacement_count: int


def _declared_from_content_type(content_type: str) -> str | None:
    m = CHARSET_RE.search(content_type or "")
    if not m:
        return None
    return m.group(1).strip().strip('"').lower()


def decode_response_bytes(
    data: bytes,
    declared_encoding: str | None = None,
    content_type: str | None = None,
    fallback_order: tuple[str, ...] = ("utf-8", "windows-1256", "cp1256", "iso-8859-6", "latin-1"),
) -> DecodeResult:
    candidates: list[str] = []
    if data.startswith(codecs.BOM_UTF8):
        candidates.append("utf-8-sig")
    declared = declared_encoding or _declared_from_content_type(content_type or "")
    if declared:
        candidates.append(declared)
    candidates.extend(fallback_order)
    try:
        from charset_normalizer import from_bytes

        best = from_bytes(data).best()
        if best and best.encoding:
            candidates.append(best.encoding)
    except Exception:
        pass
    seen: set[str] = set()
    best_text = data.decode("utf-8", errors="replace")
    best_encoding = "utf-8"
    best_replacements = best_text.count("\ufffd")
    for enc in candidates:
        if not enc or enc in seen:
            continue
        seen.add(enc)
        try:
            text = data.decode(enc, errors="replace")
        except LookupError:
            continue
        replacements = text.count("\ufffd")
        if replacements < best_replacements:
            best_text, best_encoding, best_replacements = text, enc, replacements
        if replacements == 0:
            return DecodeResult(text=text, encoding_used=enc, replacement_count=0)
    return DecodeResult(
        text=best_text, encoding_used=best_encoding, replacement_count=best_replacements
    )
