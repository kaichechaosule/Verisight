from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


COMMON_SEARCH_FIELDS = {
    "allowed_domains",
    "excluded_domains",
    "from_date",
    "to_date",
    "time_range",
    "country",
    "language",
    "safe_search",
    "include_raw_content",
    "include_answer",
    "max_results",
    "query",
}


class StrictProviderOptions(BaseModel):
    """Base model for typed provider-specific options."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def reject_common_search_fields(cls, value: Any) -> Any:
        if isinstance(value, dict):
            conflicts = sorted(COMMON_SEARCH_FIELDS.intersection(value))
            if conflicts:
                joined = ", ".join(conflicts)
                raise ValueError(f"provider options must not override common search fields: {joined}")
        return value


class TavilyOptions(StrictProviderOptions):
    search_depth: Literal["basic", "advanced"] | None = None
    topic: Literal["general", "news"] | None = None
    chunks_per_source: int | None = Field(default=None, ge=1, le=10)
    include_images: bool | None = None
    include_image_descriptions: bool | None = None
    auto_parameters: bool | None = None


class ExaOptions(StrictProviderOptions):
    type: Literal["keyword", "neural", "auto"] | None = None
    category: str | None = None
    livecrawl: Literal["always", "fallback", "never"] | None = None
    include_text: list[str] | None = None
    exclude_text: list[str] | None = None
    highlights: bool | None = None
    summary: bool | None = None
    subpages: int | None = Field(default=None, ge=0, le=10)


class BraveOptions(StrictProviderOptions):
    result_filter: list[Literal["web", "news", "videos", "images"]] | None = None
    spellcheck: bool | None = None
    text_decorations: bool | None = None
    extra_snippets: bool | None = None
    offset: int | None = Field(default=None, ge=0)


class DuckDuckGoOptions(StrictProviderOptions):
    backend: Literal["auto", "html", "lite", "bing"] | None = None
    page: int | None = Field(default=None, ge=1)


class JinaOptions(StrictProviderOptions):
    format: Literal["markdown", "text", "html"] | None = None
    selector: str | None = None
    no_cache: bool | None = None


class ProviderOptionsMap(BaseModel):
    """Provider-specific options keyed by provider name."""

    model_config = ConfigDict(extra="forbid")

    tavily: TavilyOptions | None = None
    exa: ExaOptions | None = None
    brave: BraveOptions | None = None
    duckduckgo: DuckDuckGoOptions | None = None
    jina: JinaOptions | None = None

    def for_provider(self, provider_name: str) -> BaseModel | None:
        return getattr(self, provider_name, None)

    def selected_provider_names(self) -> list[str]:
        return [name for name in type(self).model_fields if getattr(self, name) is not None]

    def applied_for(self, provider_name: str) -> dict[str, Any]:
        options = self.for_provider(provider_name)
        if options is None:
            return {}
        return options.model_dump(exclude_none=True)


PROVIDER_OPTION_MODELS = {
    "tavily": TavilyOptions,
    "exa": ExaOptions,
    "brave": BraveOptions,
    "duckduckgo": DuckDuckGoOptions,
    "jina": JinaOptions,
}


PROVIDER_CONSUMED_OPTION_KEYS = {
    "tavily": {
        "search_depth",
        "topic",
        "chunks_per_source",
        "include_images",
        "include_image_descriptions",
        "auto_parameters",
    },
    "exa": {
        "type",
        "category",
        "livecrawl",
        "include_text",
        "exclude_text",
        "highlights",
        "summary",
        "subpages",
    },
    "brave": {
        "result_filter",
        "spellcheck",
        "text_decorations",
        "extra_snippets",
        "offset",
    },
    "duckduckgo": {
        "backend",
    },
}


def split_consumed_provider_options(provider_name: str, options: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    consumed_keys = PROVIDER_CONSUMED_OPTION_KEYS.get(provider_name, set())
    applied = {key: value for key, value in options.items() if key in consumed_keys}
    ignored = {
        key: "provider option is validated but not implemented by this provider yet"
        for key in options
        if key not in consumed_keys
    }
    return applied, ignored


def provider_option_schemas() -> dict[str, dict[str, Any]]:
    return {
        name: model.model_json_schema()
        for name, model in PROVIDER_OPTION_MODELS.items()
    }


def provider_option_schema(provider_name: str) -> dict[str, Any]:
    model = PROVIDER_OPTION_MODELS.get(provider_name)
    if model is None:
        return {}
    return model.model_json_schema()


def parse_provider_options_text(value: str | None) -> ProviderOptionsMap | None:
    if value is None or not value.strip():
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"provider options must be valid JSON: {exc.msg}") from exc
    return parse_provider_options_payload(payload)


def parse_provider_options_file(path: str | None) -> ProviderOptionsMap | None:
    if path is None or not path.strip():
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"provider options file could not be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"provider options file must contain valid JSON: {exc.msg}") from exc
    return parse_provider_options_payload(payload)


def parse_provider_options_payload(payload: object) -> ProviderOptionsMap:
    if not isinstance(payload, dict):
        raise ValueError("provider options must be a JSON object keyed by provider name")
    try:
        return ProviderOptionsMap.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def merge_provider_options(
    inline_options: ProviderOptionsMap | None,
    file_options: ProviderOptionsMap | None,
) -> ProviderOptionsMap | None:
    if inline_options is None:
        return file_options
    if file_options is None:
        return inline_options
    merged = file_options.model_dump(exclude_none=True)
    for provider_name, options in inline_options.model_dump(exclude_none=True).items():
        merged[provider_name] = options
    return ProviderOptionsMap.model_validate(merged)
