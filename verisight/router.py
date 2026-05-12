from __future__ import annotations

from verisight.provider_options import ProviderOptionsMap
from verisight.schema import ProviderCapabilities, RouteResponse, SearchConstraints, SearchMode


def infer_mode(query: str, requested_mode: SearchMode | None) -> SearchMode:
    if requested_mode:
        return requested_mode
    normalized = query.lower()
    if any(token in normalized for token in ["verify", "fact check", "is it true", "是否真实", "核实"]):
        return SearchMode.verify
    if any(token in normalized for token in ["latest", "news", "breaking", "today", "最近", "最新"]):
        return SearchMode.news
    if any(token in normalized for token in ["github", "api", "docs", "documentation", "代码", "文档"]):
        return SearchMode.code
    if any(token in normalized for token in ["deep", "research", "compare", "analysis", "深入", "研究", "对比"]):
        return SearchMode.research
    return SearchMode.search


def route_query(
    query: str,
    available_providers: set[str],
    requested_mode: SearchMode | None = None,
    constraints: SearchConstraints | None = None,
    provider_options: ProviderOptionsMap | None = None,
    capabilities_by_provider: dict[str, ProviderCapabilities] | None = None,
) -> RouteResponse:
    mode = infer_mode(query, requested_mode)
    preferred = provider_preferences(mode)
    selected, reasons = rank_providers(
        preferred,
        available_providers,
        constraints,
        provider_options,
        capabilities_by_provider or {},
    )
    return RouteResponse(
        query=query,
        selected_mode=mode,
        selected_providers=selected,
        reason=routing_reason(mode, selected),
        confidence=0.85 if selected else 0.0,
        routing_reason=reasons,
    )


def rank_providers(
    preferred: list[str],
    available_providers: set[str],
    constraints: SearchConstraints | None,
    provider_options: ProviderOptionsMap | None,
    capabilities_by_provider: dict[str, ProviderCapabilities],
) -> tuple[list[str], list[str]]:
    explicit_option_providers = set(provider_options.selected_provider_names() if provider_options else [])
    scored: list[tuple[int, int, str]] = []
    reasons: list[str] = []
    for provider in sorted(explicit_option_providers - available_providers):
        reasons.append(f"{provider}: provider-specific options were supplied but the provider is not available for search.")
    for base_rank, provider in enumerate(preferred):
        if provider not in available_providers:
            continue
        score = 0
        if provider in explicit_option_providers:
            score += 100
            reasons.append(f"{provider}: prioritized because provider-specific options were supplied.")
        capability_score = native_constraint_score(constraints, capabilities_by_provider.get(provider))
        if capability_score:
            score += capability_score * 10
            reasons.append(f"{provider}: matched {capability_score} native requested constraint(s).")
        scored.append((-score, base_rank, provider))
    return [provider for _score, _rank, provider in sorted(scored)], reasons


def native_constraint_score(constraints: SearchConstraints | None, capabilities: ProviderCapabilities | None) -> int:
    if constraints is None or capabilities is None:
        return 0
    score = 0
    if (constraints.allowed_domains or constraints.excluded_domains) and capabilities.native_domains:
        score += 1
    if (constraints.from_date or constraints.to_date) and capabilities.native_date_range:
        score += 1
    if constraints.time_range and capabilities.native_time_range:
        score += 1
    if constraints.country and capabilities.native_country:
        score += 1
    if constraints.language and capabilities.native_language:
        score += 1
    if constraints.safe_search and capabilities.native_safe_search:
        score += 1
    if constraints.include_raw_content and capabilities.native_raw_content:
        score += 1
    if constraints.include_answer and capabilities.native_answer:
        score += 1
    return score


def provider_preferences(mode: SearchMode) -> list[str]:
    if mode == SearchMode.news:
        return ["brave", "tavily", "exa", "duckduckgo"]
    if mode == SearchMode.code:
        return ["exa", "brave", "tavily", "duckduckgo"]
    if mode == SearchMode.research:
        return ["exa", "tavily", "brave", "duckduckgo"]
    if mode == SearchMode.deep:
        return ["exa", "tavily", "brave", "duckduckgo"]
    if mode == SearchMode.verify:
        return ["brave", "exa", "tavily", "duckduckgo"]
    return ["exa", "brave", "tavily", "duckduckgo"]


def routing_reason(mode: SearchMode, providers: list[str]) -> str:
    if not providers:
        return "No configured search providers are available."
    if mode == SearchMode.code:
        return "Technical query routed toward semantic/docs-friendly providers first."
    if mode == SearchMode.news:
        return "Freshness-oriented query routed toward broad real-time web providers."
    if mode == SearchMode.research:
        return "Research query routed to multiple providers for coverage and cross-checking."
    if mode == SearchMode.deep:
        return "Deep mode uses all available search providers for maximum coverage."
    if mode == SearchMode.verify:
        return "Verification mode favors source diversity and contradiction discovery."
    return "General search routed to the strongest available providers."
