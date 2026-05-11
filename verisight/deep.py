from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlparse

from verisight.schema import DeepSearchIteration, EvidenceEdge, ExtractedEvidence, SearchItem, SearchConstraints


STOPWORDS = {
    "about",
    "after",
    "against",
    "also",
    "and",
    "api",
    "are",
    "compare",
    "deep",
    "docs",
    "for",
    "from",
    "how",
    "into",
    "latest",
    "mode",
    "news",
    "search",
    "the",
    "their",
    "this",
    "with",
    "what",
    "when",
    "where",
    "why",
}

# Official source domain hints
OFFICIAL_DOMAIN_HINTS = (
    ".gov",
    ".gov.",
    "docs.",
    "developer.",
    "developers.",
    "github.com",
    "official",
)

# Contradiction signal patterns
CONTRADICTION_SIGNALS = (
    "false",
    "incorrect",
    "not true",
    "no longer",
    "deprecated",
    "correction",
    "controversy",
    "debunked",
    "misleading",
    "retracted",
    "denied",
    "dispute",
    "refute",
)


def detect_gaps(
    original_query: str,
    results: list[SearchItem],
    extracted: list[ExtractedEvidence],
) -> dict[str, bool]:
    """Detect information gaps that warrant follow-up queries."""
    gaps = {}

    # Gap 1: Missing official source
    has_official = False
    for result in results:
        domain = result.domain or urlparse(result.url).netloc
        for hint in OFFICIAL_DOMAIN_HINTS:
            if hint in domain.lower():
                has_official = True
                break
        if has_official:
            break
    gaps["missing_official_source"] = not has_official

    # Gap 2: Missing contradiction evidence
    has_contradiction = False
    for result in results:
        text = f"{result.title} {result.snippet}".lower()
        for signal in CONTRADICTION_SIGNALS:
            if signal in text:
                has_contradiction = True
                break
        if has_contradiction:
            break
    for item in extracted:
        text = item.content.lower()
        for signal in CONTRADICTION_SIGNALS:
            if signal in text:
                has_contradiction = True
                break
        if has_contradiction:
            break
    gaps["missing_contradiction"] = not has_contradiction

    # Gap 3: Temporal query detected
    temporal_patterns = [
        r"\b(in\s+\d{4})\b",
        r"\b(by\s+\d{4})\b",
        r"\b(before\s+\d{4})\b",
        r"\b(after\s+\d{4})\b",
        r"\b(since\s+\d{4})\b",
        r"\b(\d{4})\b",
        r"\b(yesterday|today|tomorrow)\b",
        r"\b(last\s+week|next\s+week)\b",
        r"\b(last\s+month|next\s+month)\b",
        r"\b(last\s+year|next\s+year)\b",
    ]
    has_temporal = False
    for pattern in temporal_patterns:
        if re.search(pattern, original_query, re.IGNORECASE):
            has_temporal = True
            break
    gaps["temporal_query"] = has_temporal

    # Gap 4: Exact numeric/date signals in query
    numeric_patterns = [
        r"\b(\d+(?:\.\d+)?%)\b",
        r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\b",
        r"\b(hundreds|thousands|millions|billions)\b",
    ]
    has_numeric = False
    for pattern in numeric_patterns:
        if re.search(pattern, original_query):
            has_numeric = True
            break
    gaps["exact_numeric_signal"] = has_numeric

    # Gap 5: Low source diversity
    domains = set()
    for result in results:
        domain = result.domain or urlparse(result.url).netloc
        if domain:
            domains.add(domain.lower())
    gaps["low_source_diversity"] = len(domains) < 3

    # Gap 6: Limited evidence count
    gaps["limited_evidence"] = len(results) < 5

    return gaps


def generate_gap_driven_followups(
    original_query: str,
    results: list[SearchItem],
    extracted: list[ExtractedEvidence],
    gaps: dict[str, bool],
    explored_queries: set[str],
    limit: int,
    constraints: SearchConstraints | None = None,
) -> list[str]:
    """Generate follow-up queries based on detected gaps."""
    if limit <= 0:
        return []

    candidates: list[str] = []

    # Gap-driven follow-ups
    if gaps.get("missing_official_source"):
        for domain in (constraints.allowed_domains if constraints else []):
            candidates.append(f"site:{domain} {original_query}")
        candidates.append(f"{original_query} official documentation")
        candidates.append(f"{original_query} site:github.com")
        candidates.append(f"{original_query} docs OR documentation")

    if gaps.get("missing_contradiction"):
        candidates.append(f"{original_query} false OR incorrect OR debunked")
        candidates.append(f"{original_query} controversy OR dispute")
        candidates.append(f"{original_query} correction OR retracted")

    if gaps.get("temporal_query"):
        if constraints and constraints.from_date:
            candidates.append(f"{original_query} after:{constraints.from_date[:10]}")
        if constraints and constraints.to_date:
            candidates.append(f"{original_query} before:{constraints.to_date[:10]}")
        # Extract year from query for temporal follow-up
        year_match = re.search(r"\b(\d{4})\b", original_query)
        if year_match:
            year = year_match.group(1)
            candidates.append(f"{original_query} {year} update")
            candidates.append(f"{original_query} {year} news")
        candidates.append(f"{original_query} latest OR recent")

    if gaps.get("exact_numeric_signal"):
        candidates.append(f"{original_query} statistics OR data")
        candidates.append(f"{original_query} report OR study")
        candidates.append(f"{original_query} source OR citation")

    if gaps.get("low_source_diversity"):
        # Add site-specific queries for diverse sources
        diverse_sites = ["wikipedia.org", "scholar.google.com", "news"]
        for site in diverse_sites[:2]:
            candidates.append(f"{original_query} site:{site}")

    if gaps.get("limited_evidence"):
        keywords = _top_keywords(results, extracted, limit=3)
        if keywords:
            candidates.append(f"{original_query} {' '.join(keywords)}")

    # Deduplicate and filter
    unique: list[str] = []
    seen = {query.lower() for query in explored_queries}
    for query in candidates:
        normalized = " ".join(query.split())
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
        if len(unique) >= limit:
            break
    return unique


def generate_follow_up_queries(
    original_query: str,
    results: list[SearchItem],
    extracted: list[ExtractedEvidence],
    explored_queries: set[str],
    limit: int,
    constraints: SearchConstraints | None = None,
) -> list[str]:
    """Generate follow-up queries combining keyword-based and gap-driven approaches."""
    if limit <= 0:
        return []

    # Detect gaps first
    gaps = detect_gaps(original_query, results, extracted)

    # Generate gap-driven follow-ups (higher priority)
    gap_followups = generate_gap_driven_followups(
        original_query, results, extracted, gaps, explored_queries, limit, constraints
    )

    # Generate keyword-based follow-ups (fallback)
    candidates: list[str] = []
    domains = _top_domains(results, limit=3)
    keywords = _top_keywords(results, extracted, limit=5)
    if keywords:
        candidates.append(f"{original_query} {' '.join(keywords[:3])}")
    for domain in domains:
        candidates.append(f"site:{domain} {original_query}")
    if keywords:
        candidates.append(f"{original_query} evidence {' '.join(keywords[:2])}")
        candidates.append(f"{original_query} contradiction OR limitations {' '.join(keywords[:2])}")

    # Combine gap-driven and keyword-based, prioritizing gap-driven
    all_candidates = gap_followups + candidates

    # Deduplicate and filter
    unique: list[str] = []
    seen = {query.lower() for query in explored_queries}
    for query in all_candidates:
        normalized = " ".join(query.split())
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
        if len(unique) >= limit:
            break
    return unique


def build_evidence_graph(original_query: str, iterations: list[DeepSearchIteration]) -> dict[str, object]:
    edges: list[EvidenceEdge] = []
    nodes: dict[str, dict[str, object]] = {
        "query:root": {"id": "query:root", "type": "query", "label": original_query}
    }
    for iteration in iterations:
        for query_result in iteration.query_results:
            query = query_result.query
            query_id = f"query:{abs(hash(query))}"
            nodes[query_id] = {"id": query_id, "type": "query", "label": query, "iteration": iteration.iteration}
            for result in query_result.results:
                result_id = result.id
                nodes[result_id] = {
                    "id": result_id,
                    "type": "result",
                    "title": result.title,
                    "url": result.url,
                    "provider": result.provider,
                }
                edges.append(EvidenceEdge(source_id=query_id, target_id=result_id, url=result.url, relation="found"))
        extracted_urls = {item.url for item in iteration.extracted}
        for result in iteration.results:
            if result.url in extracted_urls:
                extraction_id = f"extract:{result.id}"
                nodes[extraction_id] = {"id": extraction_id, "type": "operation", "label": "extract"}
                edges.append(EvidenceEdge(source_id=result.id, target_id=extraction_id, url=result.url, relation="extracted"))
    return {
        "root_query": original_query,
        "nodes": list(nodes.values()),
        "edges": [edge.model_dump() for edge in edges],
    }


def _top_domains(results: list[SearchItem], limit: int) -> list[str]:
    counts: Counter[str] = Counter()
    for result in results:
        domain = result.domain or urlparse(result.url).netloc
        if domain:
            counts[domain] += 1
    return [domain for domain, _count in counts.most_common(limit)]


def _top_keywords(
    results: list[SearchItem],
    extracted: list[ExtractedEvidence],
    limit: int,
) -> list[str]:
    text = "\n".join(
        [item.title + " " + item.snippet for item in results]
        + [item.content[:2000] for item in extracted]
    ).lower()
    tokens = re.findall(r"[a-z][a-z0-9_-]{3,}", text)
    counts = Counter(token for token in tokens if token not in STOPWORDS and not token.startswith("http"))
    return [token for token, _count in counts.most_common(limit)]
