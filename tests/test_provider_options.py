import json
import tempfile
import unittest

import typer

from verisight.broker import SearchBroker
from verisight.cli import parse_provider_options
from verisight.provider_options import (
    ProviderOptionsMap,
    merge_provider_options,
    parse_provider_options_payload,
    parse_provider_options_text,
)
from verisight.schema import ProviderCapabilities, SearchItem, SearchMode, SearchRequest


class RecordingProvider:
    name = "tavily"

    def __init__(self) -> None:
        self.last_request: SearchRequest | None = None

    def available(self) -> bool:
        return True

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return False

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(native_answer=True)

    async def search(self, request: SearchRequest) -> list[SearchItem]:
        self.last_request = request
        return [
            SearchItem(
                id="tavily:1:https://example.com",
                title="Example",
                url="https://example.com",
                snippet="example",
                provider=self.name,
            )
        ]


class ProviderOptionsModelTests(unittest.TestCase):
    def test_parses_typed_provider_options(self) -> None:
        options = parse_provider_options_text('{"tavily":{"search_depth":"advanced"},"exa":{"livecrawl":"fallback"}}')

        self.assertIsNotNone(options)
        self.assertEqual(options.applied_for("tavily"), {"search_depth": "advanced"})
        self.assertEqual(options.applied_for("exa"), {"livecrawl": "fallback"})

    def test_rejects_unknown_provider(self) -> None:
        with self.assertRaisesRegex(ValueError, "extra_forbidden"):
            parse_provider_options_payload({"unknown": {"enabled": True}})

    def test_rejects_unknown_provider_option(self) -> None:
        with self.assertRaisesRegex(ValueError, "extra_forbidden"):
            parse_provider_options_payload({"tavily": {"unsupported": True}})

    def test_rejects_common_search_field_conflict(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not override common search fields"):
            parse_provider_options_payload({"tavily": {"include_answer": False}})

    def test_inline_options_override_file_options_when_merged(self) -> None:
        file_options = ProviderOptionsMap.model_validate({"tavily": {"search_depth": "basic"}, "exa": {"summary": True}})
        inline_options = ProviderOptionsMap.model_validate({"tavily": {"search_depth": "advanced"}})

        merged = merge_provider_options(inline_options, file_options)

        self.assertIsNotNone(merged)
        self.assertEqual(merged.applied_for("tavily"), {"search_depth": "advanced"})
        self.assertEqual(merged.applied_for("exa"), {"summary": True})


class ProviderOptionsCliTests(unittest.TestCase):
    def test_parse_provider_options_reads_file_and_inline_json(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump({"exa": {"summary": True}}, handle)
            path = handle.name

        options = parse_provider_options('{"tavily":{"search_depth":"advanced"}}', path)

        self.assertIsNotNone(options)
        self.assertEqual(options.applied_for("tavily"), {"search_depth": "advanced"})
        self.assertEqual(options.applied_for("exa"), {"summary": True})

    def test_parse_provider_options_raises_bad_parameter_for_invalid_json(self) -> None:
        with self.assertRaises(typer.BadParameter):
            parse_provider_options("{not-json", None)


class ProviderOptionsBrokerTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_passes_provider_options_and_reports_diagnostics(self) -> None:
        provider = RecordingProvider()
        broker = SearchBroker({"tavily": provider})
        options = ProviderOptionsMap.model_validate({"tavily": {"search_depth": "advanced"}})

        response = await broker.search("query", SearchMode.search, ["tavily"], 5, provider_options=options)

        self.assertEqual(provider.last_request.provider_options_for("tavily"), {"search_depth": "advanced"})
        self.assertEqual(response.diagnostics[0].provider_options_applied, {"search_depth": "advanced"})
        self.assertTrue(any("provider-specific options" in reason for reason in response.routing["routing_reason"]))

    async def test_implemented_brave_options_are_reported_as_applied(self) -> None:
        class BraveRecordingProvider(RecordingProvider):
            name = "brave"

        provider = BraveRecordingProvider()
        broker = SearchBroker({"brave": provider})
        options = ProviderOptionsMap.model_validate({"brave": {"spellcheck": True}})

        response = await broker.search("query", SearchMode.search, ["brave"], 5, provider_options=options)

        self.assertEqual(response.diagnostics[0].provider_options_applied, {"spellcheck": True})
        self.assertEqual(response.diagnostics[0].provider_options_ignored, {})

    async def test_unimplemented_duckduckgo_page_option_is_reported_as_ignored(self) -> None:
        class DuckDuckGoRecordingProvider(RecordingProvider):
            name = "duckduckgo"

        provider = DuckDuckGoRecordingProvider()
        broker = SearchBroker({"duckduckgo": provider})
        options = ProviderOptionsMap.model_validate({"duckduckgo": {"backend": "html", "page": 2}})

        response = await broker.search("query", SearchMode.search, ["duckduckgo"], 5, provider_options=options)

        self.assertEqual(response.diagnostics[0].provider_options_applied, {"backend": "html"})
        self.assertEqual(
            response.diagnostics[0].provider_options_ignored,
            {"page": "provider option is validated but not implemented by this provider yet"},
        )


if __name__ == "__main__":
    unittest.main()
