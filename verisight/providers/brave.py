from __future__ import annotations

from urllib.parse import urlparse

import httpx

from verisight.providers.base import ProviderConfig, ProviderError, raise_for_provider
from verisight.schema import ProviderCapabilities, SearchItem, SearchRequest


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

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_date_range=True,
            native_time_range=True,
            native_country=True,
            native_language=True,
            native_safe_search=True,
            native_news=True,
        )

    async def search(self, request: SearchRequest) -> list[SearchItem]:
        if not self.config.api_key:
            raise ProviderError("BRAVE_API_KEY is not set")

        params: dict[str, str | int | bool] = {
            "q": request.query,
            "count": min(request.max_results, 20),
            "spellcheck": "0",
        }
        if request.country:
            params["country"] = request.country
        if request.language:
            search_lang = _brave_search_language(request.language)
            params["search_lang"] = search_lang
            ui_lang = _brave_ui_language(request.language, request.country, search_lang)
            if ui_lang:
                params["ui_lang"] = ui_lang
        if request.safe_search:
            params["safesearch"] = request.safe_search
        freshness = _brave_freshness(request)
        if freshness:
            params["freshness"] = freshness
        brave_options = request.provider_options_for(self.name)
        if brave_options.get("result_filter"):
            params["result_filter"] = ",".join(brave_options["result_filter"])
        elif request.mode.value == "news":
            params["result_filter"] = "news"
        if "spellcheck" in brave_options:
            params["spellcheck"] = "1" if brave_options["spellcheck"] else "0"
        for option_key, param_key in (
            ("text_decorations", "text_decorations"),
            ("extra_snippets", "extra_snippets"),
            ("offset", "offset"),
        ):
            if option_key in brave_options:
                params[param_key] = brave_options[option_key]

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params=params,
                headers={"Accept": "application/json", "X-Subscription-Token": self.config.api_key},
            )
        raise_for_provider(response, self.name)
        web_results = response.json().get("web", {}).get("results", [])
        items: list[SearchItem] = []
        for index, item in enumerate(web_results[:request.max_results], start=1):
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


def _brave_freshness(request: SearchRequest) -> str | None:
    if request.from_date and request.to_date:
        return f"{request.from_date}to{request.to_date}"
    if request.time_range == "day":
        return "pd"
    if request.time_range == "week":
        return "pw"
    if request.time_range == "month":
        return "pm"
    if request.time_range == "year":
        return "py"
    return None


def _brave_search_language(language: str) -> str:
    normalized = language.lower().replace("_", "-")
    if normalized in {"zh", "zh-cn", "zh-sg", "zh-hans"}:
        return "zh-hans"
    if normalized in {"zh-tw", "zh-hk", "zh-mo", "zh-hant"}:
        return "zh-hant"
    return normalized


def _brave_ui_language(language: str, country: str | None, search_lang: str) -> str | None:
    normalized = language.lower().replace("_", "-")
    if search_lang == "zh-hans":
        return "zh-CN"
    if search_lang == "zh-hant":
        return "zh-TW"
    if normalized == "en":
        return "en-US"
    if len(normalized) == 2 and country:
        return f"{normalized}-{country.upper()}"
    return None
