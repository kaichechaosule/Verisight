import unittest

from verisight.router import route_query
from verisight.provider_options import ProviderOptionsMap
from verisight.schema import ProviderCapabilities, SearchConstraints, SearchMode


class RouterTests(unittest.TestCase):
    def test_routes_docs_queries_to_code_mode(self) -> None:
        route = route_query("OpenCode API docs", {"exa", "brave"})

        self.assertEqual(route.selected_mode, SearchMode.code)
        self.assertEqual(route.selected_providers, ["exa", "brave"])

    def test_duckduckgo_is_selected_as_last_resort_backup(self) -> None:
        route = route_query("OpenCode API docs", {"duckduckgo"})

        self.assertEqual(route.selected_mode, SearchMode.code)
        self.assertEqual(route.selected_providers, ["duckduckgo"])

    def test_reports_no_configured_providers(self) -> None:
        route = route_query("latest Grok news", set())

        self.assertEqual(route.selected_mode, SearchMode.news)
        self.assertEqual(route.selected_providers, [])
        self.assertEqual(route.confidence, 0.0)

    def test_jina_is_not_selected_for_search_routing(self) -> None:
        route = route_query("latest Grok news", {"jina"})

        self.assertEqual(route.selected_providers, [])

    def test_provider_options_prioritize_target_provider(self) -> None:
        route = route_query(
            "general search",
            {"exa", "brave", "tavily"},
            provider_options=ProviderOptionsMap.model_validate({"tavily": {"search_depth": "advanced"}}),
        )

        self.assertEqual(route.selected_providers[0], "tavily")
        self.assertIn("provider-specific options", route.routing_reason[0])

    def test_unavailable_provider_options_are_reported(self) -> None:
        route = route_query(
            "general search",
            {"duckduckgo"},
            provider_options=ProviderOptionsMap.model_validate({"tavily": {"search_depth": "advanced"}}),
        )

        self.assertEqual(route.selected_providers, ["duckduckgo"])
        self.assertTrue(any("tavily" in reason and "not available" in reason for reason in route.routing_reason))

    def test_native_capabilities_influence_provider_order(self) -> None:
        route = route_query(
            "general search",
            {"exa", "brave", "tavily"},
            constraints=SearchConstraints(country="US", language="en", safe_search="strict"),
            capabilities_by_provider={
                "exa": ProviderCapabilities(),
                "brave": ProviderCapabilities(native_country=True, native_language=True, native_safe_search=True),
                "tavily": ProviderCapabilities(native_country=True),
            },
        )

        self.assertEqual(route.selected_providers[0], "brave")
        self.assertTrue(any("matched 3 native" in reason for reason in route.routing_reason))


if __name__ == "__main__":
    unittest.main()
