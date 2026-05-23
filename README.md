# IngestForge

**Auditable AI content ingestion for Python — from web/manual sources to evidence-aware articles, provenance ledgers, RAG datasets, and configurable API exports.**

[![CI](https://github.com/Parvaz-Jamei/ingestforge/actions/workflows/ci.yml/badge.svg)](https://github.com/Parvaz-Jamei/ingestforge/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-alpha-orange)](#project-status)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/Parvaz-Jamei/IngestForge/blob/main/LICENSE)
[![Typed](https://img.shields.io/badge/typing-py.typed-blueviolet)](src/ingestforge/py.typed)

IngestForge is a lightweight, profile-driven Python library for building **reviewable ingestion pipelines**. It does not try to be a giant agent framework. It focuses on one practical workflow:

```text
URL or manual source
  -> safe fetch / manual ingest
  -> HTML extraction
  -> evidence gate
  -> structured AI article generation
  -> provenance ledger
  -> RAG chunks + dataset card
  -> optional local or REST export
```

The core design goal is simple: **make AI-assisted content ingestion reproducible, configurable, and auditable instead of hidden inside one-off scripts.**

> **Alpha note:** IngestForge `0.4.0a6` is usable for experiments, internal tools, portfolio demos, and controlled alpha workflows. It is not yet a production-grade unrestricted crawler, legal clearance engine, or complete SSRF defense layer.

## Why IngestForge exists

Most ingestion tools stop at extraction, markdown conversion, crawling, or framework-level orchestration. IngestForge focuses on the missing middle layer: turning sources into **standard packages** with evidence, provenance, language-aware structured output, and export contracts that can be tested before any live provider call.

| You need | IngestForge approach |
|---|---|
| Safer web ingestion | URL validation, redirect checks, byte caps, robots-aware policy, conservative defaults |
| Better extraction without heavy defaults | Internal extractor by default; optional Trafilatura backend for noisy pages |
| AI article generation | Provider adapters for OpenAI, DeepSeek, Gemini, and mock/offline mode |
| Configurable languages | `ai.source_language` and `ai.target_languages` with BCP 47-style tags; no fixed `fa/en` lock-in |
| Auditability | Evidence bundle hashes, provenance ledger, run manifest, data card |
| RAG export | Chunked records with language coverage and source metadata |
| Provider confidence before live calls | `ingestforge doctor providers --offline` validates payload contracts locally |
| Destination flexibility | Local export and generic REST destination with configurable templates/field maps |

## What makes it different

IngestForge is not just an HTML cleaner and not just an LLM wrapper. Its value is the **connected pipeline**:

```text
safe source intake
  + extraction backend policy
  + evidence/support checks
  + prompt registry
  + provider payload contracts
  + provenance ledger
  + RAG/data-card outputs
  + release hygiene tests
```

That combination is intentionally narrow, testable, and easy to embed in your own products.

## Core features in v0.4.0a6

| Area | Status |
|---|---|
| Manual URL ingestion | Implemented |
| Safe HTTP fetch | Implemented with alpha security limits |
| Robots-aware policy | Implemented as a crawling signal, not legal permission |
| HTML extraction | Internal BeautifulSoup-based extractor + optional Trafilatura backend |
| Standard package object | Implemented with typed models |
| Evidence bundle hash | Implemented |
| Provenance ledger | Implemented as an audit/provenance-inspired ledger |
| RAG export | Implemented |
| Data card generation | Implemented |
| Prompt registry | Implemented; unknown `prompt_version` fails clearly |
| Multi-language output | Configurable BCP 47-style language tags, no allowlist lock-in |
| OpenAI provider | Payload-contract tested; live calls require explicit config |
| DeepSeek provider | JSON output + explicit thinking-control payload; live calls require explicit config |
| Gemini provider | Current and legacy structured-output payload styles tested |
| Provider doctor | Offline contract validation and opt-in live smoke path |
| Generic REST destination | Implemented with configurable payload templates and response maps |
| OCR | Noop default; optional Tesseract route behind extras |
| Vision ranking | Local heuristic; AI vision remains experimental/roadmap |
| File/CSV/JSON ingestion | Roadmap |
| Fully automated publishing | Not default; human review is expected |

## Installation

Install the base package:

```bash
pip install ingestforge
```

For high-quality optional HTML extraction with Trafilatura:

```bash
pip install "ingestforge[extraction]"
```

For development:

```bash
git clone https://github.com/Parvaz-Jamei/ingestforge.git
cd ingestforge
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Quick start: CLI

Create starter files:

```bash
ingestforge init
```

Validate a profile:

```bash
ingestforge validate-profile profiles/manual_safe.yaml
```

Run a safe dry-run ingestion:

```bash
ingestforge ingest-url https://example.com/article \
  --profile profiles/manual_safe.yaml \
  --dry-run \
  --external-calls disabled
```

Validate the generated package and export RAG records:

```bash
ingestforge validate-package runs/<job_id>/package.json
ingestforge export-rag runs/<job_id>
```

Check provider contracts without spending API credits:

```bash
ingestforge doctor providers \
  --profile src/ingestforge/profiles/strict_industrial.yaml \
  --offline
```

## Quick start: Python API

Minimal use:

```python
from ingestforge import ingest_url

package = ingest_url(
    "https://example.com/article",
    dry_run=True,
    external_calls="disabled",
    write_dataset=True,
)

print(package.article.title.language_map())
```

Profile-based use:

```python
from ingestforge import pipeline

pipe = pipeline("profiles/strict_industrial.yaml")
package = pipe.ingest_url(
    "https://example.com/article",
    dry_run=True,
    external_calls="disabled",
    write_dataset=True,
)
```

## Configuration model

IngestForge is designed to be **config-driven**. Provider names, model IDs, endpoint paths, destination fields, prompt versions, language tags, limits, and safety policies are profile/env values rather than hard-coded runtime assumptions.

Configuration precedence:

```text
library defaults -> profile file / inheritance -> environment variables -> CLI overrides -> Python API overrides
```

Example profile fragment:

```yaml
profile_name: controlled_ingestion
pipeline:
  external_calls: disabled
  dry_run: true

fetch:
  allowed_domains:
    - example.com
  max_bytes: 2000000
  follow_redirects: true

extraction:
  backend: auto        # auto | internal | trafilatura
  include_tables: true
  include_comments: false
  min_extracted_chars: 40

ai:
  provider: mock
  model: mock
  prompt_version: article_builder.v1
  source_language: auto
  target_languages: [en, fa]
```

Environment override example:

```bash
export INGESTFORGE_TARGET_LANGUAGES="fa,en,de,pt-BR,zh-Hant,es-419"
export INGESTFORGE_SOURCE_LANGUAGE="auto"
```

## Extraction backends

The default extractor is intentionally dependency-light. For stronger extraction on noisy or complex pages, install the optional Trafilatura backend:

```bash
pip install "ingestforge[extraction]"
```

Then choose one of these profile modes:

```yaml
extraction:
  backend: auto         # use Trafilatura when available, fallback to internal
```

```yaml
extraction:
  backend: internal     # always use the built-in BeautifulSoup-based extractor
```

```yaml
extraction:
  backend: trafilatura  # require Trafilatura; no silent internal fallback
```

`auto` is recommended for most alpha users because it improves extraction when the optional dependency is installed while preserving a small base install.

## Provider model policy

Live model IDs are intentionally treated as **opaque provider strings**. IngestForge does not maintain a hard-coded allowlist of model names.

Model resolution order:

```text
explicit profile model
  -> INGESTFORGE_<PROVIDER>_MODEL
  -> INGESTFORGE_AI_MODEL
  -> mock only when provider is mock
  -> clear config error for live providers when external AI calls are enabled
```

Examples:

```bash
export INGESTFORGE_AI_PROVIDER=openai
export INGESTFORGE_OPENAI_MODEL="your-openai-model-id"
```

```bash
export INGESTFORGE_AI_PROVIDER=gemini
export INGESTFORGE_GEMINI_MODEL="your-gemini-model-id"
```

```bash
export INGESTFORGE_AI_PROVIDER=deepseek
export INGESTFORGE_DEEPSEEK_MODEL="your-deepseek-model-id"
```

No paid provider call is executed by the normal test suite.

## Provider doctor

Use provider doctor before live provider usage:

```bash
ingestforge doctor providers --profile profiles/examples/openai_live.yaml --offline
```

Offline mode checks local profile validity, provider payload shape, prompt resolution, and schema contract behavior.

Live smoke tests are opt-in and require credentials:

```bash
export INGESTFORGE_RUN_LIVE_PROVIDER_TESTS=1
export INGESTFORGE_OPENAI_API_KEY="..."
export INGESTFORGE_OPENAI_MODEL="..."
ingestforge doctor providers --profile profiles/examples/openai_live.yaml --live
```

## Output languages

IngestForge supports configurable output languages through BCP 47-style tags.

```yaml
ai:
  source_language: auto
  target_languages:
    - en
    - fa
    - de
    - pt-BR
    - zh-Hant
    - es-419
```

The library validates language-tag shape rather than maintaining a fixed language allowlist. This keeps the core future-proof while still catching empty or malformed values.

## Prompt registry

`ai.prompt_version` resolves to packaged prompt templates:

```yaml
ai:
  prompt_version: article_builder.v1
```

`article_builder.v1` maps to:

```text
src/ingestforge/prompts/article_builder.j2
```

Unknown prompt versions fail during profile validation instead of silently falling back to a hidden default.

## Destination adapters

The public core contains generic destination adapters only:

- `local_export` for offline package/dataset output;
- `generic_rest` for configurable API publishing with endpoint maps, payload templates, field maps, and response maps.

Private project profiles, real production API endpoints, and secrets should stay outside the public repository.

## Generated artifacts

A typical run can produce:

```text
runs/<job_id>/
  package.json
  data_card.json
  rag_records.jsonl
  provenance_ledger.jsonl
  run_manifest.json
  audit_log.jsonl
```

These artifacts are designed to make review and downstream dataset construction easier.

## Security and safety model

IngestForge is conservative by default:

- no automatic publishing;
- human review is expected;
- source license status defaults to `needs_review`;
- raw HTML is not sent to AI by default;
- private, localhost, loopback, and link-local network targets are blocked by default;
- response bodies are streamed with byte caps;
- secrets are read from environment variables, not committed profiles.

Important limitation: URL preflight validation does **not** fully eliminate DNS rebinding / TOCTOU risk because the HTTP client may resolve DNS separately from the validation step. High-security deployments should combine IngestForge checks with network egress controls, strict allowlists, and infrastructure-level protections.

## Claim and evidence limits

The current evidence gate is intentionally conservative and shallow. Exact support checks are useful for alpha review workflows, but they are **not semantic proof** and should not be marketed as legal, factual, or scientific verification.

Use IngestForge as an auditable ingestion tool, not as an authority that guarantees truth or reuse rights.

## Project status

`0.4.0a6` is an alpha release.

Best current uses:

- personal/internal ingestion experiments;
- portfolio and research-software demonstrations;
- controlled RAG dataset preparation;
- provider payload contract experiments;
- audited content workflow prototypes.

Not recommended yet for:

- unrestricted crawling at scale;
- unsupervised publishing;
- legal clearance decisions;
- high-security network environments without extra egress controls;
- claims of semantic fact verification.

## Development and release checks

Run the full local check suite:

```bash
python -m compileall -q src tests
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy src/ingestforge
python -m build --sdist --wheel
python -m twine check dist/*
python scripts/release_hygiene_check.py
```

The repository also includes GitHub Actions for CI and package publishing. PyPI/TestPyPI publishing should use Trusted Publishing where possible rather than long-lived upload tokens.

## Repository layout

```text
src/ingestforge/        library source
src/ingestforge/core/   config, pipeline, prompts, provider doctor
src/ingestforge/datasets/  RAG export, chunking, data card
src/ingestforge/providers/ provider adapters
src/ingestforge/providers/fetch/   safe fetch, robots policy, encoding, extraction
src/ingestforge/destinations/ destination adapters
docs/                   contracts and release notes
profiles/               example user profiles
tests/                  regression and contract tests
```

## Roadmap

Near-term priorities:

- stronger extraction evaluation fixtures;
- file, CSV, JSON, and PDF ingestion paths;
- deeper semantic support checks without overclaiming;
- more destination examples;
- richer documentation and examples;
- optional live provider smoke-test guides.

## Citation

See [`CITATION.cff`](https://github.com/Parvaz-Jamei/IngestForge/blob/main/CITATION.cff). If you use IngestForge in research software, dataset construction, or portfolio demonstrations, cite the repository or release tag.

## License

MIT License. See [`LICENSE`](https://github.com/Parvaz-Jamei/IngestForge/blob/main/LICENSE).
