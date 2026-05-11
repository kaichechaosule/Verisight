from __future__ import annotations

from urllib.parse import urlparse

import httpx

from verisight.providers.base import ProviderConfig, ProviderError, raise_for_provider
from verisight.schema import SearchItem


class BraveProvider:
    name = "brave"

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
            raise ProviderError("BRAVE_API_KEY is not set")

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results},
                headers={"Accept": "application/json", "X-Subscription-Token": self.config.api_key},
            )
        raise_for_provider(response, self.name)
        web_results = response.json().get("web", {}).get("results", [])
        items: list[SearchItem] = []
        for index, item in enumerate(web_results[:max_results], start=1):
            url = str(item.get("url") or "")
            if not url:
                continue
            items.append(
                SearchItem(
                    id=f"brave:{index}:{url}",
                    title=str(item.get("title") or url),
                    url=url,
                    snippet=str(item.get("description") or ""),
                    provider=self.name,
                    score=1.0 / index,
                    published_at=item.get("age"),
                    domain=urlparse(url).netloc,
                    metadata={"rank": index},
                )
            )
        return items
