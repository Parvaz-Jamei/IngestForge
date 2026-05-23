# Changelog

## 0.4.0a6

- Added optional Trafilatura-backed HTML extraction with `extraction.backend: auto|internal|trafilatura`.
- Added `ingestforge[extraction]` optional dependency extra.
- Recorded extraction backend diagnostics and source `extraction_method` in pipeline output.
- Documented that the alpha claim gate remains exact-match based, not semantic verification.
- Added config-driven `ai.source_language` and `ai.target_languages` with structural BCP 47-style validation and no provider-language allowlist.
- Hardened `strict_live_template.yaml` by rejecting empty domain values such as unset `${env:INGESTFORGE_ALLOWED_DOMAIN}`.
- Removed hard-coded live model defaults from the strict profile; offline defaults use mock/mock.
- Added generic provider model policy: model IDs are opaque strings and live providers require explicit non-empty models when external AI calls are enabled.
- Added provider doctor diagnostics for local payload contract validation.
- Added current/legacy Gemini structured-output payload styles behind explicit config.
- Made DeepSeek thinking control explicit and added OpenAI-SDK-compatible extra_body helper.
- Fixed approximate token chunking to slice original text spans for multilingual source preservation.
- Added provider contract matrix and release provider checklist.
- Documented SSRF validate-mode DNS-rebinding/TOCTOU limitations honestly.
- Added a real packaged prompt registry so `ai.prompt_version` resolves to `src/ingestforge/prompts/*.j2` at runtime and unknown prompt versions fail clearly.
- Polished CLI boolean flags so release help does not expose confusing `--no-no-*` or `--no-offline` aliases.
- Polished release metadata for PyPI and Zenodo: aligned `CITATION.cff` license with MIT, added ORCID/abstract/keywords, made README license/citation links absolute, and added a PyPI environment to Trusted Publishing.

## 0.4.0a5

- Hardened SSRF strict-allowlist semantics and documentation.
- Added robust HTML byte decoding metadata for multilingual pages.
- Replaced misleading token/word chunking with explicit tokenizer abstraction.
- Fixed package hash ordering so dataset records are included before hashing.
- Made Python API write semantics explicit through `write_dataset`.
- Added conservative claim-gate statuses and content-policy extension points.
- Added `.gitignore` and updated release hygiene expectations.

## 0.4.0a4

- Support target narrowed and documented as Python 3.11 through 3.14.
- GitHub CI matrix expanded to Linux, Windows, and macOS across Python 3.11, 3.12, 3.13, and 3.14.
- Added short public API helpers: `ingestforge.pipeline()` and `ingestforge.ingest_url()`.
- Updated packaging metadata, Ruff target, MyPy target, docs, examples, release checks, and hygiene rules for public alpha distribution.
- Removed generated caches and old build artifacts from source delivery.

## 0.4.0a1

- First clean public alpha under the IngestForge name.
- Brand-neutral package/import/CLI layout.
- Standard package contract, provenance ledger, evidence gate, reflection gate, data card generation, RAG export, and generic REST destination adapter.
