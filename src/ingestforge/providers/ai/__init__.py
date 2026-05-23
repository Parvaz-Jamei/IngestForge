from ingestforge.core.registry import registry
from ingestforge.providers.ai.deepseek_provider import DeepSeekProvider
from ingestforge.providers.ai.gemini_provider import GeminiProvider
from ingestforge.providers.ai.mock_provider import MockAIProvider
from ingestforge.providers.ai.openai_provider import OpenAIProvider

registry.register_ai("mock", MockAIProvider)
registry.register_ai("openai", OpenAIProvider)
registry.register_ai("deepseek", DeepSeekProvider)
registry.register_ai("gemini", GeminiProvider)

__all__ = ["MockAIProvider", "OpenAIProvider", "DeepSeekProvider", "GeminiProvider"]
