from __future__ import annotations

import asyncio
import importlib.util
from urllib.parse import urlparse

from verisight.providers.base import ProviderConfig, ProviderError
from verisight.schema import SearchItem


class DuckDuckGoProvider:
    name = "duckduckgo"

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def available(self) -> bool:
        return importlib.util.find_spec("ddgs") is not None

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return False

    async def search(self, query: str, max_results: int) -> list[SearchItem]:
        try:
            return await asyncio.to_thread(self._search_sync, query, max_results)
        except Exception as exc:
            raise ProviderError(f"DuckDuckGo search failed: {exc}") from exc

    def _search_sync(self, query: str, max_results: int) -> list[SearchItem]:
        try:
            from ddgs import DDGS
        except ImportError as exc:
            raise ProviderError("DuckDuckGo provider requires the optional ddgs package") from exc

        with DDGS(timeout=int(self.config.timeout_seconds)) as ddgs:
            results = list(
                ddgs.text(
                    query,
                    region="wt-wt",
                    safesearch="moderate",
                    backend="auto",
                    max_results=max_results,
                )
            )

        items: list[SearchItem] = []
        for index, item in enumerate(results[:max_results], start=1):
            url = str(item.get("href") or item.get("url") or "")
            if not url:
                continue
            title = str(item.get("title") or url)
            snippet = str(item.get("body") or item.get("snippet") or "")
            items.append(
                SearchItem(
                    id=f"duckduckgo:{index}:{url}",
                    title=title,
                    url=url,
                    snippet=snippet,
                    provider=self.name,
                    score=1.0 / index,
                    domain=urlparse(url).netloc,
                    metadata={"rank": index, "backend": "ddgs:auto"},
                )
            )
        return items
