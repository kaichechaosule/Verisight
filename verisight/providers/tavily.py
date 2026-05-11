from __future__ import annotations

from urllib.parse import urlparse

import httpx

from verisight.providers.base import ProviderConfig, ProviderError, raise_for_provider
from verisight.schema import SearchItem


class TavilyProvider:
    name = "tavily"

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def available(self) -> bool:
        return bool(self.config.api_key)

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return False

    async def search(self, query: str, max_results: int) -> list[SearchItem]:
        if not self.config.api_key:
            raise ProviderError("TAVILY_API_KEY is not set")

        payload = {
            "api_key": self.config.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": False,
        }
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post("https://api.tavily.com/search", json=payload)
        raise_for_provider(response, self.name)
        results = response.json().get("results", [])
        items: list[SearchItem] = []
        for index, item in enumerate(results[:max_results], start=1):
            url = str(item.get("url") or "")
            if not url:
                continue
            items.append(
                SearchItem(
                    id=f"tavily:{index}:{url}",
                    title=str(item.get("title") or url),
                    url=url,
                    snippet=str(item.get("content") or ""),
                    content=item.get("raw_content"),
                    provider=self.name,
                    score=item.get("score") or 1.0 / index,
                    published_at=item.get("published_date"),
                    domain=urlparse(url).netloc,
                    metadata={"rank": index},
                )
            )
        return items
