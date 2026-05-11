from __future__ import annotations

from urllib.parse import urlparse

import httpx

from verisight.providers.base import ProviderConfig, ProviderError, raise_for_provider
from verisight.schema import SearchItem


class ExaProvider:
    name = "exa"

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
            raise ProviderError("EXA_API_KEY is not set")

        payload = {
            "query": query,
            "numResults": max_results,
            "type": "auto",
            "contents": {"highlights": True, "summary": False},
        }
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(
                "https://api.exa.ai/search",
                json=payload,
                headers={"x-api-key": self.config.api_key},
            )
        raise_for_provider(response, self.name)
        results = response.json().get("results", [])
        items: list[SearchItem] = []
        for index, item in enumerate(results[:max_results], start=1):
            url = str(item.get("url") or "")
            if not url:
                continue
            highlights = item.get("highlights") or []
            snippet = "\n".join(str(value) for value in highlights[:2]) or str(item.get("text") or "")[:500]
            items.append(
                SearchItem(
                    id=f"exa:{index}:{url}",
                    title=str(item.get("title") or url),
                    url=url,
                    snippet=snippet,
                    content=str(item.get("text")) if item.get("text") else None,
                    provider=self.name,
                    score=item.get("score") or 1.0 / index,
                    published_at=item.get("publishedDate"),
                    domain=urlparse(url).netloc,
                    metadata={"rank": index, "highlights": highlights},
                )
            )
        return items
