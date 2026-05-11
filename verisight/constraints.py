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
) -> SearchConstraints | None:
    """Build SearchConstraints from CLI options."""
    if source_profile not in SOURCE_PROFILES:
        raise ValueError("source profile must be one of: balanced, official, community")
    allowed = parse_domain_list(allowed_domains)
    excluded = parse_domain_list(excluded_domains)
    if not allowed and not excluded and not from_date and not to_date and not strict and source_profile == "balanced":
        return None
    return SearchConstraints(
        allowed_domains=allowed,
        excluded_domains=excluded,
        from_date=from_date,
        to_date=to_date,
        strict_mode=strict,
        source_profile=source_profile,
    )
