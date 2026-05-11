import unittest

from verisight.router import route_query
from verisight.schema import SearchMode


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


if __name__ == "__main__":
    unittest.main()
