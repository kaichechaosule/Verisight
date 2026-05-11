from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from verisight.broker import SearchBroker
from verisight.constraints import build_constraints
from verisight.config import load_settings
from verisight.output import to_json_text
from verisight.registry import build_providers
from verisight.router import route_query
from verisight.schema import SearchMode

app = typer.Typer(add_completion=False, no_args_is_help=True)


def broker() -> SearchBroker:
    return SearchBroker(build_providers(load_settings()))


def print_json(value: object, compact: bool = False) -> None:
    """Print JSON output, optionally in compact mode."""
    try:
        typer.echo(to_json_text(value, compact=compact))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def providers() -> None:
    search_broker = broker()
    data = [
        {
            "name": name,
            "available": provider.available(),
            "supports_search": provider.supports_search(),
            "supports_extract": provider.supports_extract(),
        }
        for name, provider in search_broker.providers.items()
    ]
    print_json({"providers": data})


@app.command()
def route(
    query: Annotated[str, typer.Argument(help="Search query to route")],
    mode: Annotated[SearchMode | None, typer.Option("--mode")] = None,
) -> None:
    search_broker = broker()
    response = route_query(query, set(search_broker.available_provider_names()), mode)
    print_json(response)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Network search query")],
    mode: Annotated[SearchMode | None, typer.Option("--mode")] = None,
    providers: Annotated[str | None, typer.Option("--providers", help="Comma-separated provider names")] = None,
    max_results: Annotated[int, typer.Option("--max-results", min=1, max=50)] = 10,
    allowed_domains: Annotated[str | None, typer.Option("--allowed-domains", help="Comma-separated allowed domains")] = None,
    excluded_domains: Annotated[str | None, typer.Option("--excluded-domains", help="Comma-separated excluded domains")] = None,
    from_date: Annotated[str | None, typer.Option("--from-date", help="Filter results from this date (YYYY-MM-DD)")] = None,
    to_date: Annotated[str | None, typer.Option("--to-date", help="Filter results to this date (YYYY-MM-DD)")] = None,
    source_profile: Annotated[str, typer.Option("--source-profile", help="Source profile: balanced, official, or community")] = "balanced",
    strict: Annotated[bool, typer.Option("--strict", help="Enable strict verification mode")] = False,
    compact: Annotated[bool, typer.Option("--compact", help="Output compact JSON with key fields only")] = False,
) -> None:
    constraints = build_constraints(allowed_domains, excluded_domains, from_date, to_date, strict, source_profile)
    response = asyncio.run(broker().search(query, mode, parse_provider_names(providers), max_results, constraints))
    print_json(response, compact=compact)


@app.command()
def deep(
    query: Annotated[str, typer.Argument(help="Deep multi-provider network search query")],
    max_results: Annotated[int, typer.Option("--max-results", min=1, max=50)] = 20,
    providers: Annotated[str | None, typer.Option("--providers", help="Comma-separated provider names")] = None,
    iterations: Annotated[int, typer.Option("--iterations", min=1, max=5)] = 2,
    followups: Annotated[int, typer.Option("--followups", min=0, max=5)] = 2,
    extract_top: Annotated[int, typer.Option("--extract-top", min=0, max=10)] = 3,
    extract_max_chars: Annotated[int, typer.Option("--extract-max-chars", min=1000)] = 8000,
    allowed_domains: Annotated[str | None, typer.Option("--allowed-domains", help="Comma-separated allowed domains")] = None,
    excluded_domains: Annotated[str | None, typer.Option("--excluded-domains", help="Comma-separated excluded domains")] = None,
    from_date: Annotated[str | None, typer.Option("--from-date", help="Filter results from this date (YYYY-MM-DD)")] = None,
    to_date: Annotated[str | None, typer.Option("--to-date", help="Filter results to this date (YYYY-MM-DD)")] = None,
    source_profile: Annotated[str, typer.Option("--source-profile", help="Source profile: balanced, official, or community")] = "balanced",
    strict: Annotated[bool, typer.Option("--strict", help="Enable strict mode: more iterations, followups, extraction")] = False,
    compact: Annotated[bool, typer.Option("--compact", help="Output compact JSON with key fields only")] = False,
) -> None:
    constraints = build_constraints(allowed_domains, excluded_domains, from_date, to_date, strict, source_profile)
    # Apply strict mode defaults
    if strict:
        iterations = max(iterations, 3)
        followups = max(followups, 3)
        extract_top = max(extract_top, 5)
    response = asyncio.run(
        broker().deep_search(
            query=query,
            provider_names=parse_provider_names(providers),
            max_results=max_results,
            iterations=iterations,
            followups=followups,
            extract_top=extract_top,
            extract_max_chars=extract_max_chars,
            constraints=constraints,
        )
    )
    print_json(response, compact=compact)


@app.command()
def verify(
    claim: Annotated[str, typer.Argument(help="Claim to verify with source diversity")],
    max_results: Annotated[int, typer.Option("--max-results", min=1, max=30)] = 10,
    providers: Annotated[str | None, typer.Option("--providers", help="Comma-separated provider names")] = None,
    extract_top: Annotated[int, typer.Option("--extract-top", min=0, max=10)] = 5,
    extract_max_chars: Annotated[int, typer.Option("--extract-max-chars", min=1000)] = 8000,
    allowed_domains: Annotated[str | None, typer.Option("--allowed-domains", help="Comma-separated allowed domains")] = None,
    excluded_domains: Annotated[str | None, typer.Option("--excluded-domains", help="Comma-separated excluded domains")] = None,
    from_date: Annotated[str | None, typer.Option("--from-date", help="Filter results from this date (YYYY-MM-DD)")] = None,
    to_date: Annotated[str | None, typer.Option("--to-date", help="Filter results to this date (YYYY-MM-DD)")] = None,
    source_profile: Annotated[str, typer.Option("--source-profile", help="Source profile: balanced, official, or community")] = "balanced",
    strict: Annotated[bool, typer.Option("--strict", help="Enable strict mode: more extraction, higher thresholds")] = False,
    compact: Annotated[bool, typer.Option("--compact", help="Output compact JSON with key fields only")] = False,
) -> None:
    constraints = build_constraints(allowed_domains, excluded_domains, from_date, to_date, strict, source_profile)
    # Apply strict mode defaults
    if strict:
        max_results = max(max_results, 15)
        extract_top = max(extract_top, 7)
    response = asyncio.run(
        broker().verify_claim(
            claim=claim,
            provider_names=parse_provider_names(providers),
            max_results=max_results,
            extract_top=extract_top,
            extract_max_chars=extract_max_chars,
            constraints=constraints,
        )
    )
    print_json(response, compact=compact)


@app.command()
def extract(
    url: Annotated[str, typer.Argument(help="URL to extract into markdown-like text")],
    provider: Annotated[str, typer.Option("--provider")] = "jina",
    max_chars: Annotated[int, typer.Option("--max-chars", min=1000)] = 20000,
) -> None:
    providers_by_name = build_providers(load_settings())
    selected = providers_by_name.get(provider)
    if selected is None or not selected.supports_extract() or not hasattr(selected, "extract"):
        raise typer.BadParameter(f"Provider {provider} does not support extraction")
    response = asyncio.run(selected.extract(url))
    if len(response.content) > max_chars:
        response = response.model_copy(
            update={
                "content": response.content[:max_chars],
                "metadata": {**response.metadata, "truncated": True, "original_chars": len(response.content)},
            }
        )
    print_json(response)


def parse_provider_names(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [name.strip() for name in value.split(",") if name.strip()]


if __name__ == "__main__":
    app()
