import unittest
from unittest.mock import patch

from verisight.providers.brave import BraveProvider
from verisight.providers.base import ProviderConfig
from verisight.providers.duckduckgo import DuckDuckGoProvider
from verisight.providers.exa import ExaProvider
from verisight.providers.tavily import TavilyProvider
from verisight.provider_options import ProviderOptionsMap
from verisight.schema import SearchConstraints, SearchMode, SearchRequest


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeAsyncClient:
    last_get: dict | None = None
    last_post: dict | None = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, **kwargs) -> FakeResponse:
        FakeAsyncClient.last_get = {"url": url, **kwargs}
        return FakeResponse({"web": {"results": []}})

    async def post(self, url: str, **kwargs) -> FakeResponse:
        FakeAsyncClient.last_post = {"url": url, **kwargs}
        return FakeResponse({"results": []})


class FakeDDGS:
    last_text: dict | None = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def text(self, query: str, **kwargs):
        FakeDDGS.last_text = {"query": query, **kwargs}
        return [{"href": "https://example.com", "title": "Example", "body": "Example body"}]


def last_get_params() -> dict:
    assert FakeAsyncClient.last_get is not None
    params = FakeAsyncClient.last_get["params"]
    assert isinstance(params, dict)
    return params


def last_post_json() -> dict:
    assert FakeAsyncClient.last_post is not None
    payload = FakeAsyncClient.last_post["json"]
    assert isinstance(payload, dict)
    return payload


def last_ddg_text() -> dict:
    assert FakeDDGS.last_text is not None
    return FakeDDGS.last_text


def request() -> SearchRequest:
    return SearchRequest(
        query="latest API docs",
        mode=SearchMode.news,
        max_results=7,
        constraints=SearchConstraints(
            allowed_domains=["docs.example.com"],
            excluded_domains=["spam.example.com"],
            from_date="2025-01-01",
            to_date="2025-12-31",
            time_range="week",
            country="US",
            language="en",
            safe_search="strict",
            strict_mode=True,
            include_raw_content="markdown",
            include_answer="advanced",
        ),
    )


class ProviderParamTests(unittest.IsolatedAsyncioTestCase):
    async def test_brave_maps_native_p0_params(self) -> None:
        FakeAsyncClient.last_get = None
        provider = BraveProvider(ProviderConfig("key"))

        with patch("httpx.AsyncClient", FakeAsyncClient):
            await provider.search(request())

        params = last_get_params()
        self.assertEqual(params["q"], "latest API docs")
        self.assertEqual(params["count"], 7)
        self.assertEqual(params["country"], "US")
        self.assertEqual(params["search_lang"], "en")
        self.assertEqual(params["ui_lang"], "en-US")
        self.assertEqual(params["spellcheck"], "0")
        self.assertEqual(params["safesearch"], "strict")
        self.assertEqual(params["freshness"], "2025-01-01to2025-12-31")
        self.assertEqual(params["result_filter"], "news")

    async def test_brave_maps_chinese_language_for_api(self) -> None:
        FakeAsyncClient.last_get = None
        provider = BraveProvider(ProviderConfig("key"))
        search_request = SearchRequest(
            query="andnode 云服务器",
            max_results=5,
            constraints=SearchConstraints(country="CN", language="zh"),
        )

        with patch("httpx.AsyncClient", FakeAsyncClient):
            await provider.search(search_request)

        params = last_get_params()
        self.assertEqual(params["q"], "andnode 云服务器")
        self.assertEqual(params["country"], "CN")
        self.assertEqual(params["search_lang"], "zh-hans")
        self.assertEqual(params["ui_lang"], "zh-CN")
        self.assertEqual(params["spellcheck"], "0")

    async def test_brave_maps_traditional_chinese_language_for_api(self) -> None:
        FakeAsyncClient.last_get = None
        provider = BraveProvider(ProviderConfig("key"))
        search_request = SearchRequest(
            query="andnode 雲伺服器",
            max_results=5,
            constraints=SearchConstraints(country="TW", language="zh-tw"),
        )

        with patch("httpx.AsyncClient", FakeAsyncClient):
            await provider.search(search_request)

        params = last_get_params()
        self.assertEqual(params["search_lang"], "zh-hant")
        self.assertEqual(params["ui_lang"], "zh-TW")

    async def test_brave_maps_provider_specific_options(self) -> None:
        FakeAsyncClient.last_get = None
        provider = BraveProvider(ProviderConfig("key"))
        search_request = SearchRequest(
            query="latest API docs",
            mode=SearchMode.news,
            max_results=7,
            provider_options=ProviderOptionsMap.model_validate(
                {
                    "brave": {
                        "result_filter": ["web", "news"],
                        "spellcheck": False,
                        "text_decorations": False,
                        "extra_snippets": True,
                        "offset": 10,
                    }
                }
            ),
        )

        with patch("httpx.AsyncClient", FakeAsyncClient):
            await provider.search(search_request)

        params = last_get_params()
        self.assertEqual(params["result_filter"], "web,news")
        self.assertEqual(params["spellcheck"], "0")
        self.assertFalse(params["text_decorations"])
        self.assertTrue(params["extra_snippets"])
        self.assertEqual(params["offset"], 10)

    async def test_brave_spellcheck_provider_option_can_enable_api_spellcheck(self) -> None:
        FakeAsyncClient.last_get = None
        provider = BraveProvider(ProviderConfig("key"))
        search_request = SearchRequest(
            query="andnode",
            provider_options=ProviderOptionsMap.model_validate({"brave": {"spellcheck": True}}),
        )

        with patch("httpx.AsyncClient", FakeAsyncClient):
            await provider.search(search_request)

        params = last_get_params()
        self.assertEqual(params["spellcheck"], "1")

    async def test_tavily_maps_native_p0_params(self) -> None:
        FakeAsyncClient.last_post = None
        provider = TavilyProvider(ProviderConfig("key"))

        with patch("httpx.AsyncClient", FakeAsyncClient):
            await provider.search(request())

        payload = last_post_json()
        self.assertEqual(payload["query"], "latest API docs")
        self.assertEqual(payload["max_results"], 7)
        self.assertEqual(payload["search_depth"], "advanced")
        self.assertEqual(payload["include_domains"], ["docs.example.com"])
        self.assertEqual(payload["exclude_domains"], ["spam.example.com"])
        self.assertEqual(payload["start_date"], "2025-01-01")
        self.assertEqual(payload["end_date"], "2025-12-31")
        self.assertEqual(payload["time_range"], "week")
        self.assertEqual(payload["country"], "US")
        self.assertEqual(payload["topic"], "news")
        self.assertTrue(payload["include_raw_content"])
        self.assertTrue(payload["include_answer"])

    async def test_tavily_maps_provider_specific_options(self) -> None:
        FakeAsyncClient.last_post = None
        provider = TavilyProvider(ProviderConfig("key"))
        search_request = SearchRequest(
            query="latest API docs",
            mode=SearchMode.search,
            max_results=7,
            provider_options=ProviderOptionsMap.model_validate(
                {
                    "tavily": {
                        "search_depth": "advanced",
                        "topic": "news",
                        "chunks_per_source": 3,
                        "include_images": True,
                        "include_image_descriptions": True,
                        "auto_parameters": True,
                    }
                }
            ),
        )

        with patch("httpx.AsyncClient", FakeAsyncClient):
            await provider.search(search_request)

        payload = last_post_json()
        self.assertEqual(payload["search_depth"], "advanced")
        self.assertEqual(payload["topic"], "news")
        self.assertEqual(payload["chunks_per_source"], 3)
        self.assertTrue(payload["include_images"])
        self.assertTrue(payload["include_image_descriptions"])
        self.assertTrue(payload["auto_parameters"])


    async def test_exa_maps_native_p0_params(self) -> None:
        FakeAsyncClient.last_post = None
        provider = ExaProvider(ProviderConfig("key"))

        with patch("httpx.AsyncClient", FakeAsyncClient):
            await provider.search(request())

        payload = last_post_json()
        self.assertEqual(payload["query"], "latest API docs")
        self.assertEqual(payload["numResults"], 7)
        self.assertEqual(payload["includeDomains"], ["docs.example.com"])
        self.assertEqual(payload["excludeDomains"], ["spam.example.com"])
        self.assertEqual(payload["userLocation"], "us")
        self.assertEqual(payload["startPublishedDate"], "2025-01-01")
        self.assertEqual(payload["endPublishedDate"], "2025-12-31")
        self.assertTrue(payload["contents"]["text"])
        self.assertTrue(payload["contents"]["summary"])

    async def test_exa_maps_provider_specific_options(self) -> None:
        FakeAsyncClient.last_post = None
        provider = ExaProvider(ProviderConfig("key"))
        search_request = SearchRequest(
            query="latest API docs",
            mode=SearchMode.search,
            max_results=7,
            provider_options=ProviderOptionsMap.model_validate(
                {
                    "exa": {
                        "type": "neural",
                        "category": "research paper",
                        "livecrawl": "fallback",
                        "include_text": ["Verisight"],
                        "exclude_text": ["spam"],
                        "highlights": False,
                        "summary": True,
                        "subpages": 2,
                    }
                }
            ),
        )

        with patch("httpx.AsyncClient", FakeAsyncClient):
            await provider.search(search_request)

        payload = last_post_json()
        self.assertEqual(payload["type"], "neural")
        self.assertEqual(payload["category"], "research paper")
        self.assertEqual(payload["livecrawl"], "fallback")
        self.assertEqual(payload["includeText"], ["Verisight"])
        self.assertEqual(payload["excludeText"], ["spam"])
        self.assertFalse(payload["contents"]["highlights"])
        self.assertTrue(payload["contents"]["summary"])
        self.assertEqual(payload["subpages"], 2)

    async def test_duckduckgo_maps_backend_option(self) -> None:
        FakeDDGS.last_text = None
        provider = DuckDuckGoProvider(ProviderConfig(None))
        search_request = SearchRequest(
            query="latest API docs",
            mode=SearchMode.search,
            max_results=7,
            provider_options=ProviderOptionsMap.model_validate({"duckduckgo": {"backend": "html"}}),
        )

        with patch("ddgs.DDGS", FakeDDGS):
            results = await provider.search(search_request)

        ddg_text = last_ddg_text()
        self.assertEqual(ddg_text["query"], "latest API docs")
        self.assertEqual(ddg_text["backend"], "html")
        self.assertEqual(ddg_text["max_results"], 7)
        self.assertEqual(results[0].metadata["backend"], "ddgs:html")

    async def test_duckduckgo_maps_country_and_language_to_region(self) -> None:
        FakeDDGS.last_text = None
        provider = DuckDuckGoProvider(ProviderConfig(None))
        search_request = SearchRequest(
            query="andnode 云服务器",
            max_results=7,
            constraints=SearchConstraints(country="CN", language="zh"),
        )

        with patch("ddgs.DDGS", FakeDDGS):
            await provider.search(search_request)

        self.assertEqual(last_ddg_text()["region"], "cn-zh")

    async def test_duckduckgo_defaults_country_to_known_region_language(self) -> None:
        FakeDDGS.last_text = None
        provider = DuckDuckGoProvider(ProviderConfig(None))
        search_request = SearchRequest(
            query="latest API docs",
            max_results=7,
            constraints=SearchConstraints(country="US"),
        )

        with patch("ddgs.DDGS", FakeDDGS):
            await provider.search(search_request)

        self.assertEqual(last_ddg_text()["region"], "us-en")


class RedactionTests(unittest.TestCase):
    def test_redacts_provider_error_secrets(self) -> None:
        from verisight.providers.base import redact_sensitive_text

        text = '{"api_key":"tvly-secret123","Authorization":"Bearer abc.def"}'

        redacted = redact_sensitive_text(text)

        self.assertNotIn("tvly-secret123", redacted)
        self.assertNotIn("abc.def", redacted)
        self.assertIn("[REDACTED]", redacted)


if __name__ == "__main__":
    unittest.main()
