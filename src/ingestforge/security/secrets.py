from __future__ import annotations

from ingestforge.security.redaction import redact_secrets


def looks_like_secret(text: str) -> bool:
    return redact_secrets(text) != text
