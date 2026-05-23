# Security Model

IngestForge treats network ingestion as untrusted input. It validates schemes, blocks private networks by default, re-checks redirects, applies byte caps while streaming, and avoids storing secrets in run artifacts.

## SSRF modes

`ssrf_mode=validate` blocks obvious private, loopback, link-local, reserved, multicast, metadata-network, and localhost targets before fetch and after redirect. It does **not** fully eliminate DNS rebinding / TOCTOU risk because the HTTP client may resolve DNS separately from the preflight validation step.

For untrusted arbitrary URLs in production, use `ssrf_mode=strict_allowlist`, configure `search.allowed_domains`, and add network-level egress controls. Future hardening may add resolved-IP pinning or a custom transport layer, but v0.4.0a6 does not claim complete production SSRF protection.
