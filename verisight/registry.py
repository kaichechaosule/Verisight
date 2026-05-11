from __future__ import annotations

from verisight.config import Settings
from verisight.providers import BraveProvider, DuckDuckGoProvider, ExaProvider, JinaProvider, TavilyProvider
from verisight.providers.base import ProviderConfig, SearchProvider


def build_providers(settings: Settings) -> dict[str, SearchProvider]:
    timeout = settings.timeout_seconds
    return {
        "brave": BraveProvider(ProviderConfig(settings.brave_api_key, timeout)),
        "duckduckgo": DuckDuckGoProvider(ProviderConfig(None, timeout)),
        "exa": ExaProvider(ProviderConfig(settings.exa_api_key, timeout)),
        "tavily": TavilyProvider(ProviderConfig(settings.tavily_api_key, timeout)),
        "jina": JinaProvider(ProviderConfig(settings.jina_api_key, timeout)),
    }
