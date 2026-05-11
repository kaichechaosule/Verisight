import unittest

from verisight.broker import SearchBroker
from verisight.providers.base import ProviderError
from verisight.resilience import ProviderHealthRegistry
from verisight.schema import ExtractResponse, SearchItem, SearchMode
from verisight.verify import classify_evidence
from verisight.workers import ContradictionWorker, DiscoveryWorker, ExtractionWorker, OfficialSourceWorker


class FakeSearchProvider:
    name = "fake"

    def available(self) -> bool:
        return True

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return False

    async def search(self, query: str, max_results: int) -> list[SearchItem]:
        contradiction_query = "false" in query or "correction" in query or "deprecated" in query or "controversy" in query
        content = f"{query} official docs evidence limitations"
        title = f"Official docs about {query}"
        if contradiction_query:
            content = "unrelated noise"
            title = "Unrelated page"
        return [
            SearchItem(
                id=f"fake:{query}",
                title=title,
                url=f"https://example.com/{abs(hash(query))}",
                snippet=content,
                provider=self.name,
                domain="example.com",
                score=1.0,
            )
        ]


class FakeExtractProvider:
    name = "extractor"

    def available(self) -> bool:
        return True

    def supports_search(self) -> bool:
        return False

    def supports_extract(self) -> bool:
        return True

    async def search(self, query: str, max_results: int) -> list[SearchItem]:
        return []

    async def extract(self, url: str) -> ExtractResponse:
        return ExtractResponse(url=url, provider=self.name, title="Example", content="official evidence limitations")


class FlakySearchProvider:
    name = "flaky"

    def __init__(self, failures_before_success: int, error: str = "429 Too Many Requests") -> None:
        self.failures_before_success = failures_before_success
        self.error = error
        self.calls = 0

    def available(self) -> bool:
        return True

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return False

    async def search(self, query: str, max_results: int) -> list[SearchItem]:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise ProviderError(self.error)
        return [SearchItem(id="flaky:1", title="Recovered", url="https://example.com/recovered", provider=self.name)]


class BrokerTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_without_available_providers_returns_empty_response(self) -> None:
        broker = SearchBroker({})

        response = await broker.search("xAI docs", SearchMode.search, None, 5)

        self.assertEqual(response.results, [])
        self.assertEqual(response.providers_used, [])
        self.assertEqual(response.routing["confidence"], 0.0)

    async def test_deep_search_runs_iterations_and_generates_followups(self) -> None:
        broker = SearchBroker({"fake": FakeSearchProvider(), "extractor": FakeExtractProvider()})

        response = await broker.deep_search(
            query="Grok DeepSearch",
            provider_names=["fake"],
            max_results=5,
            iterations=2,
            followups=2,
            extract_top=1,
            extract_max_chars=1000,
        )

        self.assertGreaterEqual(len(response.iterations), 1)
        self.assertEqual(response.iterations[0].queries, ["Grok DeepSearch"])
        self.assertTrue(response.iterations[0].follow_up_queries)
        self.assertTrue(response.iterations[0].extracted)
        self.assertTrue(response.evidence_graph["edges"])
        self.assertTrue(response.iterations[0].query_results)
        found_edges = [edge for edge in response.evidence_graph["edges"] if edge["relation"] == "found"]
        self.assertTrue(all(edge["source_id"].startswith("query:") for edge in found_edges))
        extracted_edges = [edge for edge in response.evidence_graph["edges"] if edge["relation"] == "extracted"]
        self.assertTrue(all(edge["source_id"].startswith("result:") for edge in extracted_edges))

    async def test_verify_claim_returns_supported_verdict(self) -> None:
        broker = SearchBroker({"fake": FakeSearchProvider(), "extractor": FakeExtractProvider()})

        response = await broker.verify_claim(
            claim="Grok DeepSearch official docs",
            provider_names=["fake"],
            max_results=5,
            extract_top=1,
            extract_max_chars=1000,
        )

        self.assertEqual(response.verdict, "supported")
        self.assertGreater(response.confidence, 0.0)
        self.assertTrue(response.supporting_evidence)
        self.assertEqual({query_set.worker for query_set in response.query_sets}, {"discovery", "official", "contradiction"})
        self.assertTrue(all(query_set.purpose for query_set in response.query_sets))

    async def test_verify_claim_without_providers_is_insufficient(self) -> None:
        broker = SearchBroker({})

        response = await broker.verify_claim(
            claim="Grok DeepSearch official docs",
            provider_names=None,
            max_results=5,
            extract_top=1,
            extract_max_chars=1000,
        )

        self.assertEqual(response.verdict, "insufficient")
        self.assertEqual(response.supporting_evidence, [])

    async def test_search_retries_retryable_provider_errors(self) -> None:
        registry = ProviderHealthRegistry()
        health = registry.get("flaky")
        health.retry_policy.max_retries = 2
        health.retry_policy.base_delay_seconds = 0
        health.retry_policy.max_delay_seconds = 0
        provider = FlakySearchProvider(failures_before_success=1)
        broker = SearchBroker({"flaky": provider}, health_registry=registry)

        response = await broker.search("retry me", SearchMode.search, ["flaky"], 5)

        self.assertEqual(provider.calls, 2)
        self.assertEqual(len(response.results), 1)
        self.assertTrue(response.diagnostics[0].ok)
        self.assertEqual(response.diagnostics[0].attempts, 2)
        self.assertEqual(response.diagnostics[0].circuit_state, "closed")

    async def test_search_opens_circuit_after_consecutive_failures(self) -> None:
        registry = ProviderHealthRegistry()
        health = registry.get("flaky")
        health.circuit_breaker.failure_threshold = 1
        health.circuit_breaker.cooldown_seconds = 60
        health.retry_policy.max_retries = 0
        provider = FlakySearchProvider(failures_before_success=10)
        broker = SearchBroker({"flaky": provider}, health_registry=registry)

        first = await broker.search("fail once", SearchMode.search, ["flaky"], 5)
        second = await broker.search("skip now", SearchMode.search, ["flaky"], 5)

        self.assertFalse(first.diagnostics[0].ok)
        self.assertEqual(first.diagnostics[0].attempts, 1)
        self.assertEqual(first.diagnostics[0].circuit_state, "open")
        self.assertFalse(second.diagnostics[0].ok)
        self.assertEqual(second.diagnostics[0].attempts, 0)
        self.assertIn("circuit is open", second.diagnostics[0].error)
        self.assertEqual(provider.calls, 1)

    def test_false_in_neutral_context_does_not_create_contradiction(self) -> None:
        item = SearchItem(
            id="neutral",
            title="Grok multi agent API docs",
            url="https://docs.example.com/grok",
            snippet="The API returns false when the parameter is invalid. Grok multi agent supports 16 agents.",
            provider="fake",
        )

        evidence = classify_evidence("Grok multi agent supports 16 agents", item, "contradiction")

        self.assertNotEqual(evidence.stance, "contradict")

    def test_contextual_contradiction_is_classified(self) -> None:
        item = SearchItem(
            id="contradiction",
            title="Grok multi agent correction",
            url="https://docs.example.com/grok",
            snippet="Correction: Grok multi agent does not support 16 agents.",
            provider="fake",
        )

        evidence = classify_evidence("Grok multi agent supports 16 agents", item, "contradiction")

        self.assertEqual(evidence.stance, "contradict")

    def test_verify_workers_generate_expected_plans(self) -> None:
        claim = "Grok multi agent supports 16 agents"

        discovery = DiscoveryWorker().plan(claim)
        official = OfficialSourceWorker().plan(claim)
        contradiction = ContradictionWorker().plan(claim)

        self.assertEqual(discovery.name, "discovery")
        self.assertIn("source", discovery.queries[1])
        self.assertEqual(official.name, "official")
        self.assertTrue(any("site:github.com" in query for query in official.queries))
        self.assertEqual(contradiction.name, "contradiction")
        self.assertTrue(any("deprecated" in query for query in contradiction.queries))

    def test_extraction_worker_plans_unique_urls(self) -> None:
        results = [
            SearchItem(id="1", title="One", url="https://example.com/a", provider="fake"),
            SearchItem(id="2", title="Two", url="https://example.com/a", provider="fake"),
            SearchItem(id="3", title="Three", url="https://example.com/b", provider="fake"),
        ]

        urls = ExtractionWorker().plan_urls(results, 2)

        self.assertEqual(urls, ["https://example.com/a", "https://example.com/b"])


if __name__ == "__main__":
    unittest.main()
