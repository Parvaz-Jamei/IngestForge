# IngestForge Provider Contract Matrix

IngestForge treats provider model IDs as opaque strings. The library validates whether a live provider has a non-empty configured model when live AI calls are enabled, but it does not maintain a stale model allowlist.

| Provider | Model policy | Structured output | Request style | Local validation | Live smoke |
|---|---|---|---|---|---|
| OpenAI | Opaque string required when live | `json_schema_strict` | Responses API: `text.format.type=json_schema`; chat-compatible shape: `response_format.type=json_schema` | Required | Optional |
| DeepSeek | Opaque string required when live | `json_object` | Raw REST: top-level `thinking`; OpenAI SDK: `extra_body.thinking` | Required | Optional |
| Gemini | Opaque string required when live | `json_schema_subset` | Current REST: `generationConfig.responseFormat.text.mimeType/schema`; current Python SDK: `config.response_format.text.mime_type/schema`; legacy REST: `generationConfig.responseMimeType/responseSchema` | Required | Optional |

Release rule: update this matrix whenever official provider payload contracts change, then run offline provider contract tests. Live smoke tests remain opt-in and must never be required for normal CI.
