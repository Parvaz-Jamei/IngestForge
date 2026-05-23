from __future__ import annotations

import re
from collections.abc import Iterable

from ingestforge.core.errors import ConfigError

# Structural BCP 47-style validation. This intentionally does not use a fixed
# language allowlist: the IANA subtag registry changes over time and provider
# language coverage differs. The library only rejects empty/malformed tags.
_BCP47_TAG_RE = re.compile(
    r"^(?:"
    r"[A-Za-z]{2,3}(?:-[A-Za-z]{3}){0,3}"
    r"(?:-[A-Za-z]{4})?"
    r"(?:-(?:[A-Za-z]{2}|[0-9]{3}))?"
    r"(?:-[A-Za-z0-9]{5,8}|-[0-9][A-Za-z0-9]{3})*"
    r"(?:-[A-WY-Za-wy-z0-9](?:-[A-Za-z0-9]{2,8})+)*"
    r"(?:-x(?:-[A-Za-z0-9]{1,8})+)?"
    r"|x(?:-[A-Za-z0-9]{1,8})+"
    r")$"
)


def normalize_language_tag(value: str, *, field_name: str = "language tag") -> str:
    """Normalize and validate a BCP 47-style language tag without a stale allowlist."""
    tag = str(value or "").strip().replace("_", "-")
    if not tag:
        raise ConfigError(f"{field_name} must not be empty")
    if not _BCP47_TAG_RE.fullmatch(tag):
        raise ConfigError(f"{field_name} must be a valid BCP 47-style language tag, got {value!r}")
    return tag


def normalize_source_language(value: str) -> str:
    tag = str(value or "").strip().replace("_", "-")
    if tag.lower() == "auto":
        return "auto"
    return normalize_language_tag(tag, field_name="ai.source_language")


def parse_language_list(value: str | Iterable[str], *, field_name: str) -> list[str]:
    """Parse comma/plus separated language lists and preserve user order."""
    raw_items = re.split(r"[,+]", value) if isinstance(value, str) else list(value)
    languages: list[str] = []
    seen: set[str] = set()
    for raw in raw_items:
        tag = normalize_language_tag(str(raw), field_name=field_name)
        key = tag.lower()
        if key in seen:
            raise ConfigError(f"{field_name} contains duplicate language tag {tag!r}")
        seen.add(key)
        languages.append(tag)
    if not languages:
        raise ConfigError(f"{field_name} must contain at least one language tag")
    return languages
