from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from verisight.provider_options import ProviderOptionsMap


class SearchMode(StrEnum):
    search = "search"
    research = "research"
    deep = "deep"
    news = "news"
    code = "code"
    verify = "verify"


class Verdict(StrEnum):
    supported = "supported"
    contradicted = "contradicted"
    partially_true = "partially_true"
    insufficient = "insufficient"
    conflicting = "conflicting"


class EvidenceStance(StrEnum):
    support = "support"
    contradict = "contradict"
    neutral = "neutral"


class SourceType(StrEnum):
    official = "official"
    academic = "academic"
    reputable_media = "reputable_media"
    web = "web"
    social = "social"
    blog = "blog"
    forum = "forum"


class ClaimType(StrEnum):
    factual = "factual"
    opinion = "opinion"
    prediction = "prediction"
    statistical = "statistical"
    causal = "causal"
    comparative = "comparative"


class SearchItem(BaseModel):
    id: str
    title: str
    url: str
    snippet: str = ""
    content: str | None = None
    provider: str
    score: float | None = None
    published_at: str | None = None
    domain: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryResultSet(BaseModel):
    query: str
    results: list[SearchItem]


class ProviderDiagnostic(BaseModel):
    provider: str
    ok: bool
    latency_ms: int | None = None
    result_count: int = 0
    error: str | None = None
    attempts: int = 1
    circuit_state: str | None = None
    native_params: list[str] = Field(default_factory=list)
    post_processed_params: list[str] = Field(default_factory=list)
    ignored_params: list[str] = Field(default_factory=list)
    provider_options_applied: dict[str, Any] = Field(default_factory=dict)
    provider_options_ignored: dict[str, str] = Field(default_factory=dict)
    provider_options_conflicts: dict[str, str] = Field(default_factory=dict)


class Citation(BaseModel):
    id: str
    url: str
    title: str
    quote: str
    provider: str


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    providers_used: list[str]
    results: list[SearchItem]
    citations: list[Citation] = Field(default_factory=list)
    diagnostics: list[ProviderDiagnostic] = Field(default_factory=list)
    routing: dict[str, Any] = Field(default_factory=dict)


class ExtractResponse(BaseModel):
    url: str
    provider: str
    title: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteResponse(BaseModel):
    query: str
    selected_mode: SearchMode
    selected_providers: list[str]
    reason: str
    confidence: float
    routing_reason: list[str] = Field(default_factory=list)


class ExtractedEvidence(BaseModel):
    url: str
    title: str | None = None
    provider: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeepSearchIteration(BaseModel):
    iteration: int
    queries: list[str]
    query_results: list[QueryResultSet] = Field(default_factory=list)
    results: list[SearchItem]
    extracted: list[ExtractedEvidence] = Field(default_factory=list)
    follow_up_queries: list[str] = Field(default_factory=list)


class EvidenceEdge(BaseModel):
    source_id: str
    target_id: str
    url: str
    relation: Literal["found", "extracted"]


class DeepSearchResponse(BaseModel):
    query: str
    mode: SearchMode
    iterations: list[DeepSearchIteration]
    results: list[SearchItem]
    citations: list[Citation] = Field(default_factory=list)
    diagnostics: list[ProviderDiagnostic] = Field(default_factory=list)
    evidence_graph: dict[str, Any] = Field(default_factory=dict)
    routing: dict[str, Any] = Field(default_factory=dict)


class ClaimFrame(BaseModel):
    """Structured representation of a parsed claim for verification."""
    original: str
    claim_type: ClaimType
    entities: list[str] = Field(default_factory=list)
    predicates: list[str] = Field(default_factory=list)
    temporal_refs: list[str] = Field(default_factory=list)
    quantitative_refs: list[str] = Field(default_factory=list)
    negated: bool = False
    confidence: float = 1.0


class EvidenceQuote(BaseModel):
    """Quote-level evidence with stance and source classification."""
    text: str
    stance: EvidenceStance
    source_type: SourceType
    relevance_score: float
    start_offset: int | None = None
    end_offset: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerifyEvidence(BaseModel):
    stance: EvidenceStance
    url: str
    title: str
    quote: str
    provider: str
    score: float
    source_type: str
    quotes: list[EvidenceQuote] = Field(default_factory=list)
    claim_frame: ClaimFrame | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerifyQuerySet(BaseModel):
    worker: str
    purpose: str | None = None
    queries: list[str]
    results: list[SearchItem]


class VerdictMetadata(BaseModel):
    """Calibrated metadata for verdict decisions."""
    evidence_count: int
    source_diversity: float
    strongest_source_type: str
    coverage_score: float
    contradiction_ratio: float
    calibration_factors: dict[str, Any] = Field(default_factory=dict)
    uncertainty_flags: list[str] = Field(default_factory=list)


class VerifyResponse(BaseModel):
    claim: str
    verdict: Verdict
    confidence: float
    reason: str
    supporting_evidence: list[VerifyEvidence] = Field(default_factory=list)
    contradicting_evidence: list[VerifyEvidence] = Field(default_factory=list)
    neutral_evidence: list[VerifyEvidence] = Field(default_factory=list)
    query_sets: list[VerifyQuerySet] = Field(default_factory=list)
    diagnostics: list[ProviderDiagnostic] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    claim_frame: ClaimFrame | None = None
    verdict_metadata: VerdictMetadata | None = None


class SearchConstraints(BaseModel):
    """Deterministic constraints for filtering and ranking search results."""
    allowed_domains: list[str] = Field(default_factory=list)
    excluded_domains: list[str] = Field(default_factory=list)
    from_date: str | None = None  # ISO 8601 date string (YYYY-MM-DD)
    to_date: str | None = None  # ISO 8601 date string (YYYY-MM-DD)
    time_range: Literal["day", "week", "month", "year"] | None = None
    strict_mode: bool = False  # Enable stricter verification parameters
    source_profile: Literal["balanced", "official", "community"] = "balanced"
    country: str | None = None
    language: str | None = None
    safe_search: Literal["off", "moderate", "strict"] | None = None
    include_raw_content: bool | Literal["markdown", "text"] = False
    include_answer: bool | Literal["basic", "advanced"] = False


class ProviderCapabilities(BaseModel):
    """Provider-native support for common search request fields."""
    native_domains: bool = False
    native_date_range: bool = False
    native_time_range: bool = False
    native_country: bool = False
    native_language: bool = False
    native_safe_search: bool = False
    native_raw_content: bool = False
    native_answer: bool = False
    native_news: bool = False


class SearchRequest(BaseModel):
    """Provider-facing search request with common P0 search parameters."""
    query: str
    mode: SearchMode = SearchMode.search
    max_results: int = 10
    constraints: SearchConstraints | None = None
    provider_options: ProviderOptionsMap | None = None

    def provider_options_for(self, provider_name: str) -> dict[str, Any]:
        if self.provider_options is None:
            return {}
        return self.provider_options.applied_for(provider_name)

    @property
    def allowed_domains(self) -> list[str]:
        return self.constraints.allowed_domains if self.constraints else []

    @property
    def excluded_domains(self) -> list[str]:
        return self.constraints.excluded_domains if self.constraints else []

    @property
    def from_date(self) -> str | None:
        return self.constraints.from_date if self.constraints else None

    @property
    def to_date(self) -> str | None:
        return self.constraints.to_date if self.constraints else None

    @property
    def time_range(self) -> Literal["day", "week", "month", "year"] | None:
        return self.constraints.time_range if self.constraints else None

    @property
    def country(self) -> str | None:
        return self.constraints.country if self.constraints else None

    @property
    def language(self) -> str | None:
        return self.constraints.language if self.constraints else None

    @property
    def safe_search(self) -> Literal["off", "moderate", "strict"] | None:
        return self.constraints.safe_search if self.constraints else None

    @property
    def include_raw_content(self) -> bool | Literal["markdown", "text"]:
        return self.constraints.include_raw_content if self.constraints else False

    @property
    def include_answer(self) -> bool | Literal["basic", "advanced"]:
        return self.constraints.include_answer if self.constraints else False


ProviderName = Literal["brave", "duckduckgo", "exa", "tavily", "jina"]
