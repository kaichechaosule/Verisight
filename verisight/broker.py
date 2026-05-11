from __future__ import annotations

import asyncio
import time

import httpx

from verisight.deep import build_evidence_graph, generate_follow_up_queries
from verisight.providers.base import ProviderError, SearchProvider
from verisight.rank import build_citations, dedupe_and_rank
from verisight.resilience import ProviderHealthRegistry
from verisight.router import route_query
from verisight.schema import (
    DeepSearchIteration,
    DeepSearchResponse,
    ExtractedEvidence,
    ProviderDiagnostic,
    QueryResultSet,
    SearchConstraints,
    SearchItem,
    SearchMode,
    SearchResponse,
    VerifyQuerySet,
    VerifyResponse,
)
from verisight.verify import (
    citations_from_verify_evidence,
    classify_evidence,
    decide_verdict,
    parse_claim,
)
from verisight.workers import ContradictionWorker, DiscoveryWorker, ExtractionWorker, OfficialSourceWorker, SearchWorker


class SearchBroker:
    def __init__(self, providers: dict[str, SearchProvider], health_registry: ProviderHealthRegistry | None = None) -> None:
        self.providers = providers
        self.health_registry = health_registry or ProviderHealthRegistry()
        self.verify_workers: list[SearchWorker] = [
            DiscoveryWorker(),
            OfficialSourceWorker(),
            ContradictionWorker(),
        ]
        self.extraction_worker = ExtractionWorker()

    def available_provider_names(self) -> list[str]:
        return [name for name, provider in self.providers.items() if provider.available() and provider.supports_search()]

    async def search(
        self,
        query: str,
        mode: SearchMode | None,
        provider_names: list[str] | None,
        max_results: int,
        constraints: SearchConstraints | None = None,
    ) -> SearchResponse:
        route = route_query(query, set(self.available_provider_names()), mode)
        selected = provider_names or route.selected_providers
        selected = [
            name
            for name in selected
            if name in self.providers and self.providers[name].available() and self.providers[name].supports_search()
        ]
        tasks = [self._search_provider(name, query, max_results) for name in selected]
        outcomes = await asyncio.gather(*tasks) if tasks else []
        results_by_provider = {name: items for name, items, _diagnostic in outcomes if items}
        diagnostics = [diagnostic for _name, _items, diagnostic in outcomes]
        ranked = dedupe_and_rank(results_by_provider, max_results, constraints)
        return SearchResponse(
            query=query,
            mode=route.selected_mode,
            providers_used=selected,
            results=ranked,
            citations=build_citations(ranked),
            diagnostics=diagnostics,
            routing=route.model_dump(),
        )

    async def deep_search(
        self,
        query: str,
        provider_names: list[str] | None,
        max_results: int,
        iterations: int,
        followups: int,
        extract_top: int,
        extract_max_chars: int,
        constraints: SearchConstraints | None = None,
    ) -> DeepSearchResponse:
        route = route_query(query, set(self.available_provider_names()), SearchMode.deep)
        selected = provider_names or route.selected_providers
        selected = [
            name
            for name in selected
            if name in self.providers and self.providers[name].available() and self.providers[name].supports_search()
        ]
        explored_queries: set[str] = set()
        frontier = [query]
        all_results_by_url: dict[str, SearchItem] = {}
        all_diagnostics: list[ProviderDiagnostic] = []
        iteration_models: list[DeepSearchIteration] = []

        for iteration_number in range(1, iterations + 1):
            current_queries = [item for item in frontier if item.lower() not in explored_queries]
            if not current_queries:
                break
            explored_queries.update(item.lower() for item in current_queries)
            search_responses = await asyncio.gather(
                *(self.search(item, SearchMode.deep, selected, max_results, constraints) for item in current_queries)
            )
            iteration_results_by_provider: dict[str, list[SearchItem]] = {}
            for response in search_responses:
                all_diagnostics.extend(response.diagnostics)
                for result in response.results:
                    iteration_results_by_provider.setdefault(result.provider, []).append(result)
            ranked = dedupe_and_rank(iteration_results_by_provider, max_results, constraints)
            query_result_sets = [
                QueryResultSet(query=response.query, results=response.results)
                for response in search_responses
            ]
            for result in ranked:
                all_results_by_url[result.url] = result
            extracted = await self._extract_top(ranked, extract_top, extract_max_chars)
            next_queries = generate_follow_up_queries(query, ranked, extracted, explored_queries, followups, constraints)
            iteration_models.append(
                DeepSearchIteration(
                    iteration=iteration_number,
                    queries=current_queries,
                    query_results=query_result_sets,
                    results=ranked,
                    extracted=extracted,
                    follow_up_queries=next_queries,
                )
            )
            frontier = next_queries

        final_ranked = dedupe_and_rank({"deep": list(all_results_by_url.values())}, max_results, constraints)
        return DeepSearchResponse(
            query=query,
            mode=SearchMode.deep,
            iterations=iteration_models,
            results=final_ranked,
            citations=build_citations(final_ranked),
            diagnostics=all_diagnostics,
            evidence_graph=build_evidence_graph(query, iteration_models),
            routing=route.model_dump(),
        )

    async def verify_claim(
        self,
        claim: str,
        provider_names: list[str] | None,
        max_results: int,
        extract_top: int,
        extract_max_chars: int,
        constraints: SearchConstraints | None = None,
    ) -> VerifyResponse:
        route = route_query(claim, set(self.available_provider_names()), SearchMode.verify)
        selected = provider_names or route.selected_providers
        selected = [
            name
            for name in selected
            if name in self.providers and self.providers[name].available() and self.providers[name].supports_search()
        ]
        query_sets: list[VerifyQuerySet] = []
        diagnostics: list[ProviderDiagnostic] = []
        all_evidence = []
        for worker in self.verify_workers:
            plan = worker.plan(claim)
            responses = await asyncio.gather(
                *(self.search(query, SearchMode.verify, selected, max_results, constraints) for query in plan.queries)
            )
            worker_results_by_url: dict[str, SearchItem] = {}
            for response in responses:
                diagnostics.extend(response.diagnostics)
                for result in response.results:
                    worker_results_by_url[result.url] = result
            worker_results = list(worker_results_by_url.values())[:max_results]
            extracted = await self._extract_top(worker_results, extract_top, extract_max_chars)
            content_by_url = {item.url: item.content for item in extracted}
            enriched_results = [
                result.model_copy(update={"content": content_by_url.get(result.url, result.content)})
                for result in worker_results
            ]
            query_sets.append(
                VerifyQuerySet(worker=plan.name, purpose=plan.purpose, queries=plan.queries, results=enriched_results)
            )
            all_evidence.extend(classify_evidence(claim, result, plan.name) for result in enriched_results)

        supporting = sorted(
            [item for item in all_evidence if item.stance == "support"], key=lambda item: item.score, reverse=True
        )
        contradicting = sorted(
            [item for item in all_evidence if item.stance == "contradict"], key=lambda item: item.score, reverse=True
        )
        neutral = sorted(
            [item for item in all_evidence if item.stance == "neutral"], key=lambda item: item.score, reverse=True
        )[:max_results]
        verdict, confidence, reason, verdict_metadata = decide_verdict(supporting + contradicting + neutral)
        claim_frame = parse_claim(claim)
        citation_evidence = (supporting + contradicting)[:max_results]
        return VerifyResponse(
            claim=claim,
            verdict=verdict,
            confidence=confidence,
            reason=reason,
            supporting_evidence=supporting[:max_results],
            contradicting_evidence=contradicting[:max_results],
            neutral_evidence=neutral,
            query_sets=query_sets,
            diagnostics=diagnostics,
            citations=citations_from_verify_evidence(citation_evidence),
            claim_frame=claim_frame,
            verdict_metadata=verdict_metadata,
        )

    async def _search_provider(
        self,
        name: str,
        query: str,
        max_results: int,
    ) -> tuple[str, list[SearchItem], ProviderDiagnostic]:
        start = time.monotonic()
        provider = self.providers[name]
        health = self.health_registry.get(name)
        if not health.can_execute():
            elapsed_ms = int((time.monotonic() - start) * 1000)
            diagnostic = ProviderDiagnostic(
                provider=name,
                ok=False,
                latency_ms=elapsed_ms,
                error=f"Provider circuit is {health.state}; skipping request.",
                attempts=0,
                circuit_state=health.state,
            )
            return name, [], diagnostic

        attempts = 0
        last_error: Exception | None = None
        max_attempts = health.retry_policy.max_retries + 1
        for attempt_index in range(max_attempts):
            attempts += 1
            try:
                items = await provider.search(query, max_results)
                elapsed_ms = int((time.monotonic() - start) * 1000)
                self.health_registry.record(name, elapsed_ms, True)
                return name, items, ProviderDiagnostic(
                    provider=name,
                    ok=True,
                    latency_ms=elapsed_ms,
                    result_count=len(items),
                    attempts=attempts,
                    circuit_state=health.state,
                )
            except (ProviderError, TimeoutError, httpx.HTTPError) as exc:
                last_error = exc
                if attempt_index >= health.retry_policy.max_retries or not health.retry_policy.is_retryable(exc):
                    break
                await asyncio.sleep(health.retry_policy.get_delay(attempt_index))

        elapsed_ms = int((time.monotonic() - start) * 1000)
        self.health_registry.record(name, elapsed_ms, False)
        diagnostic = ProviderDiagnostic(
            provider=name,
            ok=False,
            latency_ms=elapsed_ms,
            error=str(last_error) if last_error else "Provider search failed.",
            attempts=attempts,
            circuit_state=health.state,
        )
        return name, [], diagnostic

    async def _extract_top(
        self,
        results: list[SearchItem],
        extract_top: int,
        extract_max_chars: int,
    ) -> list[ExtractedEvidence]:
        if extract_top <= 0:
            return []
        extractors = [provider for provider in self.providers.values() if provider.available() and provider.supports_extract()]
        if not extractors:
            return []
        extractor = extractors[0]
        urls = self.extraction_worker.plan_urls(results, extract_top)
        tasks = [self._extract_url(extractor, url, extract_max_chars) for url in urls]
        extracted = await asyncio.gather(*tasks)
        return [item for item in extracted if item is not None]

    async def _extract_url(
        self,
        extractor: SearchProvider,
        url: str,
        max_chars: int,
    ) -> ExtractedEvidence | None:
        if not hasattr(extractor, "extract"):
            return None
        try:
            response = await extractor.extract(url)
        except (ProviderError, TimeoutError, httpx.HTTPError):
            return None
        content = response.content[:max_chars]
        metadata = dict(response.metadata)
        if len(response.content) > max_chars:
            metadata.update({"truncated": True, "original_chars": len(response.content)})
        return ExtractedEvidence(
            url=str(response.url),
            title=response.title,
            provider=response.provider,
            content=content,
            metadata=metadata,
        )
