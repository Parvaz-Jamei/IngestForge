from ingestforge.core.registry import registry
from ingestforge.providers.search.brave_provider import BraveSearchProvider
from ingestforge.providers.search.firecrawl_provider import FirecrawlSearchProvider
from ingestforge.providers.search.google_cse_provider import GoogleCSESearchProvider
from ingestforge.providers.search.manual_provider import ManualSearchProvider
from ingestforge.providers.search.tavily_provider import TavilySearchProvider

registry.register_search("manual", ManualSearchProvider)
registry.register_search("brave", BraveSearchProvider)
registry.register_search("tavily", TavilySearchProvider)
registry.register_search("firecrawl", FirecrawlSearchProvider)
registry.register_search("google_cse", GoogleCSESearchProvider)
