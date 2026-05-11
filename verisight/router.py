from __future__ import annotations

from verisight.schema import RouteResponse, SearchMode


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


def route_query(query: str, available_providers: set[str], requested_mode: SearchMode | None = None) -> RouteResponse:
    mode = infer_mode(query, requested_mode)
    preferred = provider_preferences(mode)
    selected = [provider for provider in preferred if provider in available_providers]
    return RouteResponse(
        query=query,
        selected_mode=mode,
        selected_providers=selected,
        reason=routing_reason(mode, selected),
        confidence=0.85 if selected else 0.0,
    )


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
