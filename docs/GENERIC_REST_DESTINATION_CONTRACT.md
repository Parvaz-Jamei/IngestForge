# Generic REST Destination Contract

Destination publishing is configured with endpoint, field, payload, and response maps. Private API profiles should live outside the public repository when they contain deployment-specific details.

## Payload template syntax

`GenericRestDestination` intentionally uses IngestForge's small, deterministic template resolver for payload mappings instead of a full Jinja2 runtime. A template value is resolved only when the entire string is a single variable expression:

```json
{
  "title": "{{ article.title.en }}",
  "localized_title": "{{ article.title.pt-BR }}"
}
```

Important compatibility note:

- Dotted keys are resolved by IngestForge against nested Python dictionaries.
- Language tags with hyphens, such as `pt-BR`, `zh-Hant`, or `es-419`, are valid in IngestForge payload templates.
- The same expression is **not portable to standard Jinja2 dot syntax**. In a normal Jinja2 template, `article.title.pt-BR` can be parsed like an identifier/expression rather than a dictionary key. For Jinja2-based integrations, use bracket access such as `article.title["pt-BR"]` in that external system.
- IngestForge payload templates are for exact field extraction only; they are not a general expression language.

## Undefined variables

If a payload template references a missing variable, publishing fails with a clear `DestinationError` instead of silently sending `null` or an incomplete payload.
