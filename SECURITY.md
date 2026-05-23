# Security Policy

Report vulnerabilities through GitHub Security Advisories or by opening a private contact channel with the maintainer.

Do not include API keys, destination tokens, private URLs, credentials, or run artifacts in issues.

IngestForge blocks localhost, private, link-local, multicast, reserved, and metadata-network URLs by default for URL-based ingestion. Users can loosen this only through explicit profile choices for offline/local testing.

## SSRF limitation notice

`ssrf_mode=validate` blocks obvious private, loopback, link-local, reserved, multicast, metadata-network, and localhost targets before fetch and after redirect, but it does not fully eliminate DNS rebinding / TOCTOU risk because the HTTP client may resolve DNS separately. For untrusted arbitrary URLs in production, use `strict_allowlist` and network-level egress controls.
