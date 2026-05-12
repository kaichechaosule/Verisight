import unittest
from unittest.mock import patch

from verisight.providers.brave import BraveProvider
from verisight.providers.base import ProviderConfig
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

        params = FakeAsyncClient.last_get["params"]  # type: ignore[index]
        self.assertEqual(params["q"], "latest API docs")
        self.assertEqual(params["count"], 7)
        self.assertEqual(params["country"], "US")
        self.assertEqual(params["search_lang"], "en")
        self.assertEqual(params["safesearch"], "strict")
        self.assertEqual(params["freshness"], "2025-01-01to2025-12-31")
        self.assertEqual(params["result_filter"], "news")

    async def test_tavily_maps_native_p0_params(self) -> None:
        FakeAsyncClient.last_post = None
        provider = TavilyProvider(ProviderConfig("key"))

        with patch("httpx.AsyncClient", FakeAsyncClient):
            await provider.search(request())

        payload = FakeAsyncClient.last_post["json"]  # type: ignore[index]
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

        payload = FakeAsyncClient.last_post["json"]  # type: ignore[index]
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

        payload = FakeAsyncClient.last_post["json"]  # type: ignore[index]
        self.assertEqual(payload["query"], "latest API docs")
        self.assertEqual(payload["numResults"], 7)
        self.assertEqual(payload["includeDomains"], ["docs.example.com"])
        self.assertEqual(payload["excludeDomains"], ["spam.example.com"])
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

        payload = FakeAsyncClient.last_post["json"]  # type: ignore[index]
        self.assertEqual(payload["type"], "neural")
        self.assertEqual(payload["category"], "research paper")
        self.assertEqual(payload["livecrawl"], "fallback")
        self.assertEqual(payload["includeText"], ["Verisight"])
        self.assertEqual(payload["excludeText"], ["spam"])
        self.assertFalse(payload["contents"]["highlights"])
        self.assertTrue(payload["contents"]["summary"])
        self.assertEqual(payload["subpages"], 2)


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
