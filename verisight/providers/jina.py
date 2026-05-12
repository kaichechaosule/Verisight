from __future__ import annotations

from urllib.parse import urlparse

import httpx

from verisight.providers.base import ProviderConfig, ProviderError, raise_for_provider
from verisight.schema import ExtractResponse, ProviderCapabilities, SearchItem, SearchRequest


class JinaProvider:
    name = "jina"

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def available(self) -> bool:
        return True

    def supports_search(self) -> bool:
        return False

    def supports_extract(self) -> bool:
        return True

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(native_raw_content=True)

    async def search(self, request: SearchRequest) -> list[SearchItem]:
        raise ProviderError("Jina is configured as an extraction provider, not a search provider")

    async def extract(self, url: str) -> ExtractResponse:
        headers = self._headers()
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.get(f"https://r.jina.ai/{url}", headers=headers)
        raise_for_provider(response, self.name)
        parsed = urlparse(url)
        return ExtractResponse(
            url=url,
            provider=self.name,
            title=parsed.netloc or None,
            content=response.text,
            metadata={"domain": parsed.netloc},
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "text/plain"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers
