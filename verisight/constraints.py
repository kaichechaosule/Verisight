from __future__ import annotations

from typing import Literal, cast

from verisight.schema import SearchConstraints


SOURCE_PROFILES = {"balanced", "official", "community"}
SourceProfile = Literal["balanced", "official", "community"]
TimeRange = Literal["day", "week", "month", "year"]
SafeSearch = Literal["off", "moderate", "strict"]
RawContentMode = bool | Literal["markdown", "text"]
AnswerMode = bool | Literal["basic", "advanced"]


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
    if include_raw_content not in {False, True, "markdown", "text"}:
        raise ValueError("include raw content must be a boolean, markdown, or text")
    if include_answer not in {False, True, "basic", "advanced"}:
        raise ValueError("include answer must be a boolean, basic, or advanced")
    if not allowed and not excluded and not from_date and not to_date and not strict and source_profile == "balanced" and not time_range and not country and not language and not safe_search and not include_raw_content and not include_answer:
        return None
    return SearchConstraints(
        allowed_domains=allowed,
        excluded_domains=excluded,
        from_date=from_date,
        to_date=to_date,
        time_range=cast(TimeRange | None, time_range),
        strict_mode=strict,
        source_profile=cast(SourceProfile, source_profile),
        country=country,
        language=language,
        safe_search=cast(SafeSearch | None, safe_search),
        include_raw_content=cast(RawContentMode, include_raw_content),
        include_answer=cast(AnswerMode, include_answer),
    )
