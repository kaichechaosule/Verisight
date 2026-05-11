from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from verisight.schema import Citation, SearchConstraints, SearchItem
from verisight.sources import extract_domain, matches_source_profile


TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref"}

# Date patterns for extracting publication dates from snippets
DATE_PATTERNS = [
    r"\b(\d{4}-\d{2}-\d{2})\b",  # ISO format YYYY-MM-DD
    r"\b(\d{2}/\d{2}/\d{4})\b",  # US format MM/DD/YYYY
    r"\b(\d{4})\b",  # Year only
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",  # Month DD, YYYY
    r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",  # DD Month YYYY
]

def extract_date_from_text(text: str) -> datetime | None:
    """Extract date from text using deterministic patterns."""
    if not text:
        return None
    text_lower = text.lower()

    # Try ISO format first
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso_match:
        try:
            return datetime.strptime(iso_match.group(1), "%Y-%m-%d")
        except ValueError:
            pass

    # Try year only
    year_match = re.search(r"\b(\d{4})\b", text)
    if year_match:
        year = int(year_match.group(1))
        if 1990 <= year <= datetime.now().year + 1:
            return datetime(year, 1, 1)

    return None


def apply_constraints(items: list[SearchItem], constraints: SearchConstraints | None) -> list[SearchItem]:
    """Apply deterministic constraints to filter search results."""
    if not constraints:
        return items

    filtered = []
    for item in items:
        domain = extract_domain(item.url)

        # Domain filtering
        if constraints.allowed_domains:
            allowed = False
            for allowed_domain in constraints.allowed_domains:
                if domain == allowed_domain.lower() or domain.endswith("." + allowed_domain.lower()):
                    allowed = True
                    break
            if not allowed:
                continue

        if constraints.excluded_domains:
            excluded = False
            for excluded_domain in constraints.excluded_domains:
                if domain == excluded_domain.lower() or domain.endswith("." + excluded_domain.lower()):
                    excluded = True
                    break
            if excluded:
                continue

        if not matches_source_profile(item, constraints.source_profile):
            continue

        # Date filtering
        if constraints.from_date or constraints.to_date:
            # Try to extract date from published_at field first
            item_date = None
            if item.published_at:
                try:
                    item_date = datetime.strptime(item.published_at[:10], "%Y-%m-%d")
                except ValueError:
                    pass

            # Fall back to extracting from snippet/title
            if not item_date:
                text = f"{item.title} {item.snippet}"
                item_date = extract_date_from_text(text)

            # If we have date constraints but can't extract date, keep the item
            # (conservative approach - don't filter out items we can't date)
            if item_date:
                if constraints.from_date:
                    try:
                        from_dt = datetime.strptime(constraints.from_date[:10], "%Y-%m-%d")
                        if item_date < from_dt:
                            continue
                    except ValueError:
                        pass
                if constraints.to_date:
                    try:
                        to_dt = datetime.strptime(constraints.to_date[:10], "%Y-%m-%d")
                        if item_date > to_dt:
                            continue
                    except ValueError:
                        pass

        filtered.append(item)

    return filtered


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in TRACKING_KEYS and not key.startswith(TRACKING_PREFIXES)
    ]
    normalized = parsed._replace(fragment="", query=urlencode(query))
    return urlunparse(normalized)


def dedupe_and_rank(
    provider_results: dict[str, list[SearchItem]],
    limit: int,
    constraints: SearchConstraints | None = None,
) -> list[SearchItem]:
    # First apply constraints to each provider's results
    if constraints:
        provider_results = {
            provider: apply_constraints(items, constraints)
            for provider, items in provider_results.items()
        }

    rrf_scores: dict[str, float] = defaultdict(float)
    winners: dict[str, SearchItem] = {}
    providers_by_url: dict[str, set[str]] = defaultdict(set)
    k = 60
    for provider, items in provider_results.items():
        for rank, item in enumerate(items, start=1):
            key = normalize_url(item.url)
            rrf_scores[key] += 1.0 / (k + rank)
            providers_by_url[key].add(provider)
            current = winners.get(key)
            current_score = current.score if current and current.score is not None else -1.0
            item_score = item.score if item.score is not None else 0.0
            if current is None or item_score > current_score:
                winners[key] = item.model_copy(update={"url": key})

    ranked_keys = sorted(rrf_scores, key=lambda key: rrf_scores[key], reverse=True)
    ranked: list[SearchItem] = []
    for index, key in enumerate(ranked_keys[:limit], start=1):
        item = winners[key]
        ranked.append(
            item.model_copy(
                update={
                    "id": f"result:{index}",
                    "score": rrf_scores[key],
                    "metadata": {
                        **item.metadata,
                        "providers": sorted(providers_by_url[key]),
                        "rrf_score": rrf_scores[key],
                    },
                }
            )
        )
    return ranked


def build_citations(items: list[SearchItem]) -> list[Citation]:
    citations: list[Citation] = []
    for index, item in enumerate(items, start=1):
        quote = item.snippet or (item.content or "")[:500]
        if not quote:
            continue
        citations.append(
            Citation(
                id=f"cite:{index}",
                url=item.url,
                title=item.title,
                quote=quote[:700],
                provider=item.provider,
            )
        )
    return citations
