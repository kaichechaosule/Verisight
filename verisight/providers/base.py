from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol, runtime_checkable

import httpx

from verisight.schema import ExtractResponse, ProviderCapabilities, SearchItem, SearchRequest


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderConfig:
    api_key: str | None
    timeout_seconds: float = 15.0


class SearchProvider(Protocol):
    name: str

    def available(self) -> bool:
        raise NotImplementedError

    def supports_search(self) -> bool:
        raise NotImplementedError

    def supports_extract(self) -> bool:
        raise NotImplementedError

    def capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    async def search(self, request: SearchRequest) -> list[SearchItem]:
        raise NotImplementedError


@runtime_checkable
class ExtractProvider(Protocol):
    name: str

    def available(self) -> bool:
        raise NotImplementedError

    def supports_extract(self) -> bool:
        raise NotImplementedError

    async def extract(self, url: str) -> ExtractResponse:
        raise NotImplementedError


def unsupported_params(request: SearchRequest, capabilities: ProviderCapabilities) -> tuple[list[str], list[str]]:
    """Return common request params handled natively vs requiring fallback/ignore."""
    native: list[str] = []
    fallback: list[str] = []
    if request.allowed_domains or request.excluded_domains:
        (native if capabilities.native_domains else fallback).append("domains")
    if request.from_date or request.to_date:
        (native if capabilities.native_date_range else fallback).append("date_range")
    if request.time_range:
        (native if capabilities.native_time_range else fallback).append("time_range")
    if request.country:
        (native if capabilities.native_country else fallback).append("country")
    if request.language:
        (native if capabilities.native_language else fallback).append("language")
    if request.safe_search:
        (native if capabilities.native_safe_search else fallback).append("safe_search")
    if request.include_raw_content:
        (native if capabilities.native_raw_content else fallback).append("include_raw_content")
    if request.include_answer:
        (native if capabilities.native_answer else fallback).append("include_answer")
    if request.mode.value == "news":
        (native if capabilities.native_news else fallback).append("news_mode")
    return native, fallback


def raise_for_provider(response: httpx.Response, provider: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = redact_sensitive_text(exc.response.text[:500])
        raise ProviderError(f"{provider} returned {exc.response.status_code}: {detail}") from exc


def redact_sensitive_text(text: str) -> str:
    """Redact common API key/token patterns from provider error text."""
    patterns = [
        r"tvly-[A-Za-z0-9_-]+",
        r"Bearer\s+[A-Za-z0-9._~+/=-]+",
        r"(?i)(api[_-]?key\s*[=:]\s*)[\"']?[^\s\"',}]+",
        r"(?i)(x-subscription-token\s*[=:]\s*)[\"']?[^\s\"',}]+",
        r"(?i)(authorization\s*[=:]\s*)[\"']?[^\s\"',}]+",
    ]
    redacted = text
    for pattern in patterns:
        redacted = re.sub(pattern, lambda match: match.group(1) + "[REDACTED]" if match.lastindex else "[REDACTED]", redacted)
    return redacted
