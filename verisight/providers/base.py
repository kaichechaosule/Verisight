from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from verisight.schema import SearchItem


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderConfig:
    api_key: str | None
    timeout_seconds: float = 15.0


class SearchProvider(Protocol):
    name: str

    def available(self) -> bool:
        raise NotImplementedError

    def supports_search(self) -> bool:
        raise NotImplementedError

    def supports_extract(self) -> bool:
        raise NotImplementedError

    async def search(self, query: str, max_results: int) -> list[SearchItem]:
        raise NotImplementedError


def raise_for_provider(response: httpx.Response, provider: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        raise ProviderError(f"{provider} returned {exc.response.status_code}: {detail}") from exc
