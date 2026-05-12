from __future__ import annotations

from urllib.parse import urlparse

import httpx

from verisight.providers.base import ProviderConfig, ProviderError, raise_for_provider
from verisight.schema import ProviderCapabilities, SearchItem, SearchRequest


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

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_domains=True,
            native_date_range=True,
            native_time_range=True,
            native_country=True,
            native_raw_content=True,
            native_answer=True,
            native_news=True,
        )

    async def search(self, request: SearchRequest) -> list[SearchItem]:
        if not self.config.api_key:
            raise ProviderError("TAVILY_API_KEY is not set")

        payload: dict[str, object] = {
            "api_key": self.config.api_key,
            "query": request.query,
            "max_results": request.max_results,
            "search_depth": "advanced" if request.constraints and request.constraints.strict_mode else "basic",
            "include_answer": bool(request.include_answer),
            "include_raw_content": bool(request.include_raw_content),
        }
        if request.allowed_domains:
            payload["include_domains"] = request.allowed_domains
        if request.excluded_domains:
            payload["exclude_domains"] = request.excluded_domains
        if request.from_date:
            payload["start_date"] = request.from_date
        if request.to_date:
            payload["end_date"] = request.to_date
        if request.time_range:
            payload["time_range"] = request.time_range
        if request.country:
            payload["country"] = request.country
        if request.mode.value == "news":
            payload["topic"] = "news"
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post("https://api.tavily.com/search", json=payload)
        raise_for_provider(response, self.name)
        results = response.json().get("results", [])
        items: list[SearchItem] = []
        for index, item in enumerate(results[:request.max_results], start=1):
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
