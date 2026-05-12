from __future__ import annotations

from urllib.parse import urlparse

import httpx

from verisight.providers.base import ProviderConfig, ProviderError, raise_for_provider
from verisight.schema import ProviderCapabilities, SearchItem, SearchRequest


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

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_domains=True,
            native_date_range=True,
            native_raw_content=True,
        )

    async def search(self, request: SearchRequest) -> list[SearchItem]:
        if not self.config.api_key:
            raise ProviderError("EXA_API_KEY is not set")

        exa_options = request.provider_options_for(self.name)
        payload = {
            "query": request.query,
            "numResults": request.max_results,
            "type": exa_options.get("type", "auto"),
            "contents": {
                "highlights": exa_options.get("highlights", True),
                "summary": exa_options.get("summary", bool(request.include_answer)),
                "text": bool(request.include_raw_content),
            },
        }
        for option_key, payload_key in (
            ("category", "category"),
            ("livecrawl", "livecrawl"),
            ("include_text", "includeText"),
            ("exclude_text", "excludeText"),
            ("subpages", "subpages"),
        ):
            if option_key in exa_options:
                payload[payload_key] = exa_options[option_key]
        if request.allowed_domains:
            payload["includeDomains"] = request.allowed_domains
        if request.excluded_domains:
            payload["excludeDomains"] = request.excluded_domains
        if request.from_date:
            payload["startPublishedDate"] = request.from_date
        if request.to_date:
            payload["endPublishedDate"] = request.to_date
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(
                "https://api.exa.ai/search",
                json=payload,
                headers={"x-api-key": self.config.api_key},
            )
        raise_for_provider(response, self.name)
        results = response.json().get("results", [])
        items: list[SearchItem] = []
        for index, item in enumerate(results[:request.max_results], start=1):
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
