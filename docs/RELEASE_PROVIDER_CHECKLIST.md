# Release Provider Checklist

Before every IngestForge provider-related tag:

- [ ] Re-check OpenAI official model docs and structured output docs.
- [ ] Re-check DeepSeek JSON Output and Thinking Mode docs.
- [ ] Re-check Gemini structured output docs and model support table.
- [ ] Update `docs/PROVIDER_CONTRACT_MATRIX.md` and `src/ingestforge/provider_contracts.yaml` if API shapes changed.
- [ ] Run offline provider contract tests.
- [ ] Run live provider smoke tests only if API keys are available and `INGESTFORGE_RUN_LIVE_PROVIDER_TESTS=1` is explicitly set.
- [ ] Update README claims so alpha limitations remain honest.

CI must not depend on live web browsing or paid provider calls. This checklist is a release-manager step.
