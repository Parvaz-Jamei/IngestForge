# Extraction backends

IngestForge keeps the default installation lightweight, but `HtmlExtractor` now supports a stronger optional extraction backend.

## Backends

```yaml
extraction:
  backend: auto          # default
```

| Backend | Behavior |
|---|---|
| `auto` | Uses Trafilatura if installed and it returns text; otherwise falls back to the internal BeautifulSoup extractor. |
| `internal` | Always uses the dependency-light internal extractor. |
| `trafilatura` | Uses only Trafilatura; if unavailable or empty, extraction returns empty text and the normal evidence gate can fail. |

## Install optional backend

```bash
pip install 'ingestforge[extraction]'
```

## Trafilatura options

```yaml
extraction:
  backend: auto
  include_tables: true
  include_comments: false
  trafilatura_favor_precision: false
  trafilatura_favor_recall: false
  min_extracted_chars: 40
```

`trafilatura_favor_precision` and `trafilatura_favor_recall` are mutually exclusive. IngestForge does not set Trafilatura's extraction-time `target_language` by default because IngestForge supports BCP 47-style multilingual output configuration and should not discard useful multilingual pages during extraction.

## Evidence and claim gates

A stronger extraction backend can improve `clean_text`, snippets, evidence coverage, RAG chunks, and downstream generation quality. It does **not** make generated claims semantically verified. In v0.4.0a6, the claim gate is deterministic and exact-match based; semantic verification remains a future hardening area and human-review concern.
