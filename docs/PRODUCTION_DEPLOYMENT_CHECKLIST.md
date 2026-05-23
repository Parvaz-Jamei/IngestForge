# Production Deployment Checklist

- Verify provider model names from official docs.
- Use environment variables for secrets.
- Run CI, build, twine check, and secret scan.
- Publish alpha to TestPyPI first.
- Confirm the destination profile is private and reviewed.

## Optional extraction backend hardening

For higher-quality extraction on complex HTML pages, install the optional Trafilatura backend:

```bash
pip install 'ingestforge[extraction]'
```

Recommended profile block:

```yaml
extraction:
  backend: auto          # auto = Trafilatura when installed, internal fallback otherwise
  include_tables: true
  include_comments: false
  trafilatura_favor_precision: false
  trafilatura_favor_recall: false
```

Use `backend: internal` for deterministic dependency-light runs, or `backend: trafilatura` when you want to fail clearly instead of falling back if the optional dependency is missing or returns empty text.

The extraction backend improves clean-text quality; it does not change the license gate, claim gate, SSRF model, or human-review requirement. The alpha claim gate remains deterministic and exact-match based, not semantic verification.
