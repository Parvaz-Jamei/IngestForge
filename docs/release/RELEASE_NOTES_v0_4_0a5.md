# IngestForge v0.4.0a6

Security and dataset-integrity hardening alpha.

Highlights:

- Explicit Python API write semantics (`write_dataset`).
- Conservative SSRF strict-allowlist mode and defensive URL validation tests.
- Robust response decoding metadata for multilingual pages.
- Tokenizer abstraction for chunking (`tokens`, `words`, `chars`, optional `tiktoken`).
- Package hash integrity fixed after dataset records are attached.
- Conservative claim gate and content policy extension points.
- `.gitignore` and release hygiene improvements.

This remains an alpha framework, not a production-ready crawler or automatic publisher.
