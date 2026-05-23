from __future__ import annotations

import re

SECRET_PATTERNS = [
    re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._\-]+", re.I),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{12,}", re.I),
    re.compile(r"([?&](?:api_key|token|key)=)[^&\s]+", re.I),
    re.compile(r"(api[_-]?key\s*[=:]\s*)[^\s]+", re.I),
    re.compile(r"(token\s*[=:]\s*)[^\s]+", re.I),
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
]


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        if "(?" in pattern.pattern and "api_key" in pattern.pattern:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        elif "api" in pattern.pattern.lower() or "token" in pattern.pattern.lower():
            redacted = pattern.sub(
                lambda m: (m.group(1) if m.lastindex else "") + "[REDACTED]", redacted
            )
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
