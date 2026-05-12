from __future__ import annotations

from verisight.schema import SearchConstraints


SOURCE_PROFILES = {"balanced", "official", "community"}


def parse_domain_list(value: str | None) -> list[str]:
    """Parse comma-separated domain list."""
    if not value:
        return []
    return [domain.strip().lower() for domain in value.split(",") if domain.strip()]


def build_constraints(
    allowed_domains: str | None,
    excluded_domains: str | None,
    from_date: str | None,
    to_date: str | None,
    strict: bool,
    source_profile: str = "balanced",
    time_range: str | None = None,
    country: str | None = None,
    language: str | None = None,
    safe_search: str | None = None,
    include_raw_content: bool | str = False,
    include_answer: bool | str = False,
) -> SearchConstraints | None:
    """Build SearchConstraints from CLI options."""
    if source_profile not in SOURCE_PROFILES:
        raise ValueError("source profile must be one of: balanced, official, community")
    allowed = parse_domain_list(allowed_domains)
    excluded = parse_domain_list(excluded_domains)
    if safe_search not in {None, "off", "moderate", "strict"}:
        raise ValueError("safe search must be one of: off, moderate, strict")
    if time_range not in {None, "day", "week", "month", "year"}:
        raise ValueError("time range must be one of: day, week, month, year")
    if not allowed and not excluded and not from_date and not to_date and not strict and source_profile == "balanced" and not time_range and not country and not language and not safe_search and not include_raw_content and not include_answer:
        return None
    return SearchConstraints(
        allowed_domains=allowed,
        excluded_domains=excluded,
        from_date=from_date,
        to_date=to_date,
        time_range=time_range,  # type: ignore[arg-type]
        strict_mode=strict,
        source_profile=source_profile,
        country=country,
        language=language,
        safe_search=safe_search,  # type: ignore[arg-type]
        include_raw_content=include_raw_content,
        include_answer=include_answer,
    )
