from __future__ import annotations

import re
from verisight.rank import build_citations
from verisight.schema import (
    ClaimFrame,
    ClaimType,
    EvidenceQuote,
    EvidenceStance,
    SearchItem,
    SourceType,
    Verdict,
    VerdictMetadata,
    VerifyEvidence,
)
from verisight.sources import classify_source, classify_source_type, source_credibility


CONTRADICTION_TERMS = {
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
}

TEMPORAL_PATTERNS = [
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

QUANTITATIVE_PATTERNS = [
    r"\b(\d+(?:\.\d+)?%)\b",
    r"\b(\d+(?:,\d{3})*(?:\.\d+)?(?:%| percent))\b",
    r"\b(hundreds|thousands|millions|billions)\b",
    r"\b(approximately|about|around)\s+\d+\b",
]

PREDICATE_INDICATORS = [
    "is",
    "are",
    "was",
    "were",
    "will",
    "has",
    "have",
    "had",
    "does",
    "do",
    "can",
    "could",
    "should",
    "would",
    "may",
    "might",
    "must",
    "supports",
    "proves",
    "shows",
    "demonstrates",
    "indicates",
    "suggests",
    "claims",
    "states",
    "says",
    "reports",
    "announces",
]


def parse_claim(claim: str) -> ClaimFrame:
    """Parse a claim into a structured ClaimFrame using deterministic rules."""
    claim_lower = claim.lower()
    claim_type = _classify_claim_type(claim)
    entities = _extract_entities(claim)
    predicates = _extract_predicates(claim)
    temporal_refs = _extract_temporal_refs(claim)
    quantitative_refs = _extract_quantitative_refs(claim)
    negated = _detect_negation(claim_lower)
    return ClaimFrame(
        original=claim,
        claim_type=claim_type,
        entities=entities,
        predicates=predicates,
        temporal_refs=temporal_refs,
        quantitative_refs=quantitative_refs,
        negated=negated,
        confidence=1.0,
    )


def _classify_claim_type(claim: str) -> ClaimType:
    """Classify the type of claim using deterministic patterns."""
    claim_lower = claim.lower()
    if any(word in claim_lower for word in ["believe", "think", "opinion", "feel", "seems", "appears", "arguably", "in my view", "i believe", "i think"]):
        return ClaimType.opinion
    if any(word in claim_lower for word in ["predict", "forecast", "will be", "will ", "expected to", "projected to", "estimate", "future"]):
        return ClaimType.prediction
    if any(word in claim_lower for word in ["cause", "leads to", "results in", "because", "due to", "effect", "impact"]):
        return ClaimType.causal
    if any(word in claim_lower for word in ["better", "worse", "more", "less", "higher", "lower", "compared to", "versus", "vs", "than"]):
        return ClaimType.comparative
    if any(pattern in claim_lower for pattern in ["%", "percent", "statistics", "average", "median", "rate", "ratio", "number of"]):
        return ClaimType.statistical
    return ClaimType.factual


def _extract_entities(claim: str) -> list[str]:
    """Extract named entities using simple capitalization patterns."""
    entities = []
    capitalized = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", claim)
    for entity in capitalized:
        if entity.lower() not in {"the", "this", "that", "these", "those", "a", "an", "is", "are", "was", "were", "will", "has", "have", "had", "does", "do"}:
            entities.append(entity)
    all_caps = re.findall(r"\b[A-Z]{2,}\b", claim)
    for entity in all_caps:
        if entity.lower() not in {"the", "this", "that", "these", "those", "a", "an", "is", "are", "was", "were", "will", "has", "have", "had", "does", "do"}:
            entities.append(entity)
    quoted = re.findall(r"'([^']+)'|\"([^\"]+)\"", claim)
    for match in quoted:
        if match[0]:
            entities.append(match[0])
        if match[1]:
            entities.append(match[1])
    return entities[:10]


def _extract_predicates(claim: str) -> list[str]:
    """Extract predicate verbs from the claim."""
    predicates = []
    claim_lower = claim.lower()
    for indicator in PREDICATE_INDICATORS:
        if indicator in claim_lower:
            predicates.append(indicator)
    return predicates[:5]


def _extract_temporal_refs(claim: str) -> list[str]:
    """Extract temporal references from the claim."""
    refs = []
    for pattern in TEMPORAL_PATTERNS:
        matches = re.findall(pattern, claim, re.IGNORECASE)
        refs.extend(matches)
    return refs[:5]


def _extract_quantitative_refs(claim: str) -> list[str]:
    """Extract quantitative references from the claim."""
    refs = []
    percent_matches = re.findall(r"(\d+(?:\.\d+)?%)", claim)
    refs.extend(percent_matches)
    number_matches = re.findall(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\b", claim)
    for match in number_matches:
        if match not in refs and f"{match}%" not in refs:
            refs.append(match)
    word_matches = re.findall(r"\b(hundreds|thousands|millions|billions)\b", claim, re.IGNORECASE)
    refs.extend(word_matches)
    approx_matches = re.findall(r"\b(approximately|about|around)\s+(\d+)\b", claim, re.IGNORECASE)
    for match in approx_matches:
        refs.append(f"{match[0]} {match[1]}")
    return refs[:5]


def _detect_negation(claim_lower: str) -> bool:
    """Detect if the claim contains negation."""
    negation_patterns = [
        r"\bnot\b",
        r"\bno\b",
        r"\bnever\b",
        r"\bdoesn't\b",
        r"\bdon't\b",
        r"\bwon't\b",
        r"\bcan't\b",
        r"\bcouldn't\b",
        r"\bshouldn't\b",
        r"\bwouldn't\b",
        r"\bisn't\b",
        r"\baren't\b",
        r"\bwasn't\b",
        r"\bweren't\b",
        r"\bhasn't\b",
        r"\bhaven't\b",
        r"\bhadn't\b",
        r"\bfalse\b",
        r"\bincorrect\b",
        r"\buntrue\b",
    ]
    return any(re.search(pattern, claim_lower) for pattern in negation_patterns)


def classify_evidence(claim: str, item: SearchItem, worker: str) -> VerifyEvidence:
    """Classify evidence from a SearchItem against a claim."""
    text = " ".join([item.title, item.snippet, item.content or ""]).lower()
    claim_terms = _claim_terms(claim)
    coverage = _term_coverage(text, claim_terms)
    source_type = classify_source(item.url)
    source_type_enum = classify_source_type(item.url)
    source_weight = source_credibility(source_type)
    contradiction_signal = _has_contextual_contradiction(text, claim_terms)
    score = min(1.0, (coverage * 0.75) + (source_weight * 0.25))
    if contradiction_signal and coverage >= 0.45:
        stance = EvidenceStance.contradict
    elif coverage >= 0.45:
        stance = EvidenceStance.support
    else:
        stance = EvidenceStance.neutral
        score = min(score, 0.45)
    quote_text = (item.snippet or item.content or "")[:700]
    quotes = _extract_quote_evidence(quote_text, claim_terms, source_type_enum, coverage)
    claim_frame = parse_claim(claim)
    return VerifyEvidence(
        stance=stance,
        url=item.url,
        title=item.title,
        quote=quote_text,
        provider=item.provider,
        score=round(score, 4),
        source_type=source_type,
        quotes=quotes,
        claim_frame=claim_frame,
        metadata={
            "worker": worker,
            "coverage": round(coverage, 4),
            "source_weight": source_weight,
            "contradiction_signal": contradiction_signal,
        },
    )


def _extract_quote_evidence(
    text: str,
    claim_terms: set[str],
    source_type: SourceType,
    coverage: float,
) -> list[EvidenceQuote]:
    """Extract quote-level evidence with stance detection."""
    quotes = []
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    for sentence in sentences:
        if len(sentence.strip()) < 20:
            continue
        sentence_lower = sentence.lower()
        sentence_coverage = _term_coverage(sentence_lower, claim_terms)
        if sentence_coverage < 0.25:
            continue
        stance = _detect_sentence_stance(sentence_lower, claim_terms)
        relevance_score = min(1.0, sentence_coverage * 0.7 + (0.3 if stance != EvidenceStance.neutral else 0.1))
        quotes.append(
            EvidenceQuote(
                text=sentence.strip(),
                stance=stance,
                source_type=source_type,
                relevance_score=round(relevance_score, 4),
                metadata={
                    "sentence_coverage": round(sentence_coverage, 4),
                },
            )
        )
    return quotes[:5]


def _detect_sentence_stance(sentence: str, claim_terms: set[str]) -> EvidenceStance:
    """Detect stance of a sentence relative to claim terms."""
    contradiction_patterns = [
        r"\bdoes\s+not\s+support\b",
        r"\bdo\s+not\s+support\b",
        r"\bno\s+longer\s+supports?\b",
        r"\bnot\s+supported\b",
        r"\bunsupported\b",
        r"\bincorrect\b",
        r"\bfalse\b",
        r"\bdebunked\b",
        r"\bretracted\b",
        r"\bmisleading\b",
        r"\bdenied\b",
        r"\bcontradict\b",
        r"\bdispute\b",
        r"\brefute\b",
    ]
    support_patterns = [
        r"\bconfirm\b",
        r"\bverify\b",
        r"\bprove\b",
        r"\bdemonstrate\b",
        r"\bshow\b",
        r"\bevidence\b",
        r"\bsupports?\b",
        r"\bvalid\b",
        r"\bcorrect\b",
        r"\btrue\b",
        r"\baccurate\b",
        r"\bconfirmed\b",
        r"\bproven\b",
    ]
    has_contradiction = any(re.search(pattern, sentence) for pattern in contradiction_patterns)
    has_support = any(re.search(pattern, sentence) for pattern in support_patterns)
    term_hits = sum(1 for term in claim_terms if term in sentence)
    if has_contradiction and term_hits >= 2:
        return EvidenceStance.contradict
    if has_support and term_hits >= 2:
        return EvidenceStance.support
    return EvidenceStance.neutral


def decide_verdict(evidence: list[VerifyEvidence]) -> tuple[Verdict, float, str, VerdictMetadata]:
    """Decide verdict from evidence with calibrated metadata."""
    supporting = [item for item in evidence if item.stance == EvidenceStance.support]
    contradicting = [item for item in evidence if item.stance == EvidenceStance.contradict]
    neutral = [item for item in evidence if item.stance == EvidenceStance.neutral]
    support_score = sum(item.score for item in supporting)
    contradict_score = sum(item.score for item in contradicting)
    strong_support = any(item.source_type in {"official", "academic"} and item.score >= 0.55 for item in supporting)
    strong_contradict = any(item.source_type in {"official", "academic"} and item.score >= 0.55 for item in contradicting)
    source_types = {item.source_type for item in evidence}
    source_diversity = min(1.0, len(source_types) / 4.0)
    strongest_source_type = max(
        source_types,
        key=lambda st: source_credibility(st),
        default="web",
    )
    coverage_scores = [item.metadata.get("coverage", 0.0) for item in evidence]
    avg_coverage = sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0.0
    total_evidence = len(supporting) + len(contradicting) + len(neutral)
    contradiction_ratio = len(contradicting) / total_evidence if total_evidence > 0 else 0.0
    uncertainty_flags = _detect_uncertainty_flags(evidence, supporting, contradicting)
    calibration_factors = {
        "strong_source_boost": 0.15 if strong_support or strong_contradict else 0.0,
        "source_diversity_factor": source_diversity * 0.1,
        "coverage_factor": avg_coverage * 0.05,
    }
    if support_score == 0 and contradict_score == 0:
        metadata = VerdictMetadata(
            evidence_count=total_evidence,
            source_diversity=source_diversity,
            strongest_source_type=strongest_source_type,
            coverage_score=round(avg_coverage, 4),
            contradiction_ratio=contradiction_ratio,
            calibration_factors=calibration_factors,
            uncertainty_flags=uncertainty_flags,
        )
        return Verdict.insufficient, 0.2, "No support or contradiction evidence met the minimum relevance threshold.", metadata
    if support_score > 0 and contradict_score > 0:
        if abs(support_score - contradict_score) <= 0.4 or (strong_support and strong_contradict):
            confidence = min(0.85, 0.45 + min(support_score, contradict_score) / 4)
            metadata = VerdictMetadata(
                evidence_count=total_evidence,
                source_diversity=source_diversity,
                strongest_source_type=strongest_source_type,
                coverage_score=round(avg_coverage, 4),
                contradiction_ratio=contradiction_ratio,
                calibration_factors=calibration_factors,
                uncertainty_flags=uncertainty_flags + ["conflicting_evidence"],
            )
            return Verdict.conflicting, round(confidence, 4), "Both supporting and contradicting evidence were found.", metadata
        if support_score > contradict_score:
            confidence = min(0.88, 0.5 + (support_score - contradict_score) / 3)
            metadata = VerdictMetadata(
                evidence_count=total_evidence,
                source_diversity=source_diversity,
                strongest_source_type=strongest_source_type,
                coverage_score=round(avg_coverage, 4),
                contradiction_ratio=contradiction_ratio,
                calibration_factors=calibration_factors,
                uncertainty_flags=uncertainty_flags + ["partial_support"],
            )
            return Verdict.partially_true, round(confidence, 4), "Support is stronger, but contradicting evidence also exists.", metadata
        confidence = min(0.88, 0.5 + (contradict_score - support_score) / 3)
        metadata = VerdictMetadata(
            evidence_count=total_evidence,
            source_diversity=source_diversity,
            strongest_source_type=strongest_source_type,
            coverage_score=round(avg_coverage, 4),
            contradiction_ratio=contradiction_ratio,
            calibration_factors=calibration_factors,
            uncertainty_flags=uncertainty_flags + ["partial_contradiction"],
        )
        return Verdict.contradicted, round(confidence, 4), "Contradicting evidence is stronger than support.", metadata
    if support_score > 0:
        confidence = min(0.95, 0.45 + support_score / 3 + (0.15 if strong_support else 0.0))
        metadata = VerdictMetadata(
            evidence_count=total_evidence,
            source_diversity=source_diversity,
            strongest_source_type=strongest_source_type,
            coverage_score=round(avg_coverage, 4),
            contradiction_ratio=contradiction_ratio,
            calibration_factors=calibration_factors,
            uncertainty_flags=uncertainty_flags,
        )
        return Verdict.supported, round(confidence, 4), "Relevant supporting evidence was found.", metadata
    confidence = min(0.95, 0.45 + contradict_score / 3 + (0.15 if strong_contradict else 0.0))
    metadata = VerdictMetadata(
        evidence_count=total_evidence,
        source_diversity=source_diversity,
        strongest_source_type=strongest_source_type,
        coverage_score=round(avg_coverage, 4),
        contradiction_ratio=contradiction_ratio,
        calibration_factors=calibration_factors,
        uncertainty_flags=uncertainty_flags,
    )
    return Verdict.contradicted, round(confidence, 4), "Relevant contradicting evidence was found.", metadata


def _detect_uncertainty_flags(
    evidence: list[VerifyEvidence],
    supporting: list[VerifyEvidence],
    contradicting: list[VerifyEvidence],
) -> list[str]:
    """Detect uncertainty flags from evidence patterns."""
    flags = []
    if len(evidence) < 3:
        flags.append("low_evidence_count")
    if len(supporting) == 0 and len(contradicting) == 0:
        flags.append("no_clear_stance")
    source_types = {item.source_type for item in evidence}
    if "official" not in source_types and "academic" not in source_types:
        flags.append("no_authoritative_source")
    coverage_scores = [item.metadata.get("coverage", 0.0) for item in evidence]
    if coverage_scores and max(coverage_scores) < 0.5:
        flags.append("low_coverage")
    temporal_refs = []
    for item in evidence:
        if item.claim_frame and item.claim_frame.temporal_refs:
            temporal_refs.extend(item.claim_frame.temporal_refs)
    if temporal_refs:
        flags.append("temporal_claim")
    return flags


def citations_from_verify_evidence(evidence: list[VerifyEvidence]):
    items = [
        SearchItem(
            id=f"verify:{index}",
            title=item.title,
            url=item.url,
            snippet=item.quote,
            provider=item.provider,
            score=item.score,
        )
        for index, item in enumerate(evidence, start=1)
    ]
    return build_citations(items)


def _claim_terms(claim: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9_.-]{3,}", claim.lower())
    stopwords = {"the", "and", "that", "this", "with", "from", "supports", "support", "does"}
    return {token for token in tokens if token not in stopwords}


def _term_coverage(text: str, terms: set[str]) -> float:
    if not terms:
        return 0.0
    matched = sum(1 for term in terms if term in text)
    return matched / len(terms)


def _has_contextual_contradiction(text: str, claim_terms: set[str]) -> bool:
    if not claim_terms:
        return False
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    entity_terms = {term for term in claim_terms if not term.isdigit()}
    contradiction_patterns = [
        r"\bdoes\s+not\s+support\b",
        r"\bdo\s+not\s+support\b",
        r"\bno\s+longer\s+supports?\b",
        r"\bnot\s+supported\b",
        r"\bunsupported\b",
        r"\bincorrect\b",
        r"\bdebunked\b",
        r"\bretracted\b",
        r"\bmisleading\b",
    ]
    for sentence in sentences:
        has_pattern = any(re.search(pattern, sentence) for pattern in contradiction_patterns)
        has_false_claim_pattern = re.search(r"\b(false|incorrect)\b", sentence) and re.search(
            r"\b(claim|statement|rumou?r|report|assertion)\b", sentence
        )
        if not has_pattern and not has_false_claim_pattern:
            continue
        term_hits = sum(1 for term in claim_terms if term in sentence)
        entity_hit = any(term in sentence for term in entity_terms)
        if entity_hit and term_hits >= max(2, min(3, len(claim_terms))):
            return True
    return False
