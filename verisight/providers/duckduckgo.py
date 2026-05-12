from __future__ import annotations

import asyncio
import importlib.util
from urllib.parse import urlparse

from verisight.providers.base import ProviderConfig, ProviderError
from verisight.schema import ProviderCapabilities, SearchItem, SearchRequest


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

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_time_range=True,
            native_country=True,
            native_language=True,
            native_safe_search=True,
            native_news=True,
        )

    async def search(self, request: SearchRequest) -> list[SearchItem]:
        try:
            return await asyncio.to_thread(self._search_sync, request)
        except Exception as exc:
            raise ProviderError(f"DuckDuckGo search failed: {exc}") from exc

    def _search_sync(self, request: SearchRequest) -> list[SearchItem]:
        try:
            from ddgs import DDGS
        except ImportError as exc:
            raise ProviderError("DuckDuckGo provider requires the optional ddgs package") from exc

        with DDGS(timeout=int(self.config.timeout_seconds)) as ddgs:
            duckduckgo_options = request.provider_options_for(self.name)
            kwargs = {
                "region": _ddg_region(request.country, request.language),
                "safesearch": _ddg_safesearch(request.safe_search),
                "backend": duckduckgo_options.get("backend", "auto"),
                "max_results": request.max_results,
            }
            timelimit = _ddg_timelimit(request.time_range)
            if timelimit:
                kwargs["timelimit"] = timelimit
            if request.mode.value == "news" and hasattr(ddgs, "news"):
                results = list(ddgs.news(request.query, **kwargs))
            else:
                results = list(ddgs.text(request.query, **kwargs))

        items: list[SearchItem] = []
        backend = str(kwargs["backend"])
        for index, item in enumerate(results[:request.max_results], start=1):
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
                    metadata={"rank": index, "backend": f"ddgs:{backend}"},
                )
            )
        return items


def _ddg_region(country: str | None, language: str | None = None) -> str:
    if not country:
        return "wt-wt"
    country_code = country.lower().replace("_", "-")
    if "-" in country_code:
        return country_code
    language_code = _ddg_language_code(country_code, language)
    return f"{country_code}-{language_code}"


def _ddg_language_code(country_code: str, language: str | None) -> str:
    if language:
        normalized = language.lower().replace("_", "-")
        if normalized in {"zh", "zh-cn", "zh-hans"}:
            return "zh"
        if normalized in {"zh-tw", "zh-hk", "zh-hant"}:
            return "tzh"
        return normalized.split("-", 1)[0]
    return {
        "cn": "zh",
        "hk": "tzh",
        "jp": "jp",
        "tw": "tzh",
        "uk": "en",
        "us": "en",
    }.get(country_code, country_code)


def _ddg_timelimit(time_range: str | None) -> str | None:
    return {
        "day": "d",
        "week": "w",
        "month": "m",
        "year": "y",
    }.get(time_range or "")


def _ddg_safesearch(value: str | None) -> str:
    if value == "strict":
        return "on"
    return value or "moderate"
