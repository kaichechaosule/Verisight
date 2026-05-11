"""Offline golden verify tests using synthetic SearchItem fixtures."""
import unittest

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
from verisight.verify import (
    classify_evidence,
    classify_source,
    classify_source_type,
    decide_verdict,
    parse_claim,
)


def make_search_item(
    title: str,
    url: str,
    snippet: str,
    provider: str = "test",
    content: str | None = None,
) -> SearchItem:
    """Create a synthetic SearchItem for testing."""
    return SearchItem(
        id=f"test:{hash(url)}",
        title=title,
        url=url,
        snippet=snippet,
        provider=provider,
        domain=url.split("/")[-2] if "/" in url else "example.com",
        score=1.0,
        content=content,
    )


class ClaimParsingTests(unittest.TestCase):
    """Tests for claim parsing functionality."""

    def test_parse_factual_claim(self) -> None:
        """Test parsing a factual claim."""
        claim = "Python supports async programming"
        frame = parse_claim(claim)
        self.assertEqual(frame.claim_type, ClaimType.factual)
        self.assertIn("Python", frame.entities)
        self.assertIn("supports", frame.predicates)
        self.assertFalse(frame.negated)

    def test_parse_prediction_claim(self) -> None:
        """Test parsing a prediction claim."""
        claim = "AI will transform healthcare by 2030"
        frame = parse_claim(claim)
        self.assertEqual(frame.claim_type, ClaimType.prediction)
        self.assertIn("AI", frame.entities)
        self.assertIn("2030", frame.temporal_refs)

    def test_parse_statistical_claim(self) -> None:
        """Test parsing a statistical claim."""
        claim = "50% of users prefer dark mode"
        frame = parse_claim(claim)
        self.assertEqual(frame.claim_type, ClaimType.statistical)
        self.assertIn("50%", frame.quantitative_refs)

    def test_parse_comparative_claim(self) -> None:
        """Test parsing a comparative claim."""
        claim = "React is more popular than Vue"
        frame = parse_claim(claim)
        self.assertEqual(frame.claim_type, ClaimType.comparative)
        self.assertIn("React", frame.entities)
        self.assertIn("Vue", frame.entities)

    def test_parse_causal_claim(self) -> None:
        """Test parsing a causal claim."""
        claim = "Exercise leads to better health outcomes"
        frame = parse_claim(claim)
        self.assertEqual(frame.claim_type, ClaimType.causal)

    def test_parse_opinion_claim(self) -> None:
        """Test parsing an opinion claim."""
        claim = "I believe this approach is better"
        frame = parse_claim(claim)
        self.assertEqual(frame.claim_type, ClaimType.opinion)

    def test_parse_negated_claim(self) -> None:
        """Test parsing a negated claim."""
        claim = "Python does not support static typing"
        frame = parse_claim(claim)
        self.assertTrue(frame.negated)


class SourceClassificationTests(unittest.TestCase):
    """Tests for source classification functionality."""

    def test_classify_government_source(self) -> None:
        """Test classifying government source."""
        source = classify_source("https://gov.uk/policy")
        self.assertEqual(source, SourceType.official.value)

    def test_classify_academic_source(self) -> None:
        """Test classifying academic source."""
        source = classify_source("https://arxiv.org/paper")
        self.assertEqual(source, SourceType.academic.value)

    def test_classify_edu_source(self) -> None:
        """Test classifying .edu source."""
        source = classify_source("https://stanford.edu/research")
        self.assertEqual(source, SourceType.academic.value)

    def test_classify_reputable_media(self) -> None:
        """Test classifying reputable media source."""
        source = classify_source("https://reuters.com/article")
        self.assertEqual(source, SourceType.reputable_media.value)

    def test_classify_social_source(self) -> None:
        """Test classifying social media source."""
        source = classify_source("https://twitter.com/user")
        self.assertEqual(source, SourceType.social.value)

    def test_classify_forum_source(self) -> None:
        """Test classifying forum source."""
        source = classify_source("https://reddit.com/thread")
        self.assertEqual(source, SourceType.forum.value)

    def test_classify_blog_source(self) -> None:
        """Test classifying blog source."""
        source = classify_source("https://medium.com/post")
        self.assertEqual(source, SourceType.blog.value)

    def test_classify_web_source(self) -> None:
        """Test classifying generic web source."""
        source = classify_source("https://example.com/page")
        self.assertEqual(source, SourceType.web.value)

    def test_classify_source_type_returns_enum(self) -> None:
        """Test classify_source_type returns SourceType enum."""
        source_type = classify_source_type("https://gov.uk/policy")
        self.assertEqual(source_type, SourceType.official)


class EvidenceClassificationTests(unittest.TestCase):
    """Tests for evidence classification functionality."""

    def test_classify_supporting_evidence(self) -> None:
        """Test classifying supporting evidence."""
        claim = "Python supports async programming"
        item = make_search_item(
            title="Python Async Programming Guide",
            url="https://docs.python.org/async",
            snippet="Python supports async programming with asyncio library",
        )
        evidence = classify_evidence(claim, item, "discovery")
        self.assertEqual(evidence.stance, EvidenceStance.support)
        self.assertEqual(evidence.source_type, SourceType.official.value)
        self.assertGreater(evidence.score, 0.4)

    def test_classify_contradicting_evidence(self) -> None:
        """Test classifying contradicting evidence."""
        claim = "Python supports static typing"
        item = make_search_item(
            title="Python Typing Myths Debunked",
            url="https://example.com/article",
            snippet="The claim that Python supports static typing is false. Python is dynamically typed.",
        )
        evidence = classify_evidence(claim, item, "contradiction")
        self.assertEqual(evidence.stance, EvidenceStance.contradict)

    def test_classify_neutral_evidence(self) -> None:
        """Test classifying neutral evidence."""
        claim = "Quantum computing will revolutionize cryptography"
        item = make_search_item(
            title="Introduction to Quantum Computing",
            url="https://example.com/intro",
            snippet="Quantum computing is an emerging field of research.",
        )
        evidence = classify_evidence(claim, item, "discovery")
        self.assertEqual(evidence.stance, EvidenceStance.neutral)

    def test_evidence_has_claim_frame(self) -> None:
        """Test that evidence includes claim frame."""
        claim = "Python supports async programming"
        item = make_search_item(
            title="Python Async Guide",
            url="https://docs.python.org/async",
            snippet="Python supports async programming",
        )
        evidence = classify_evidence(claim, item, "discovery")
        self.assertIsNotNone(evidence.claim_frame)
        self.assertEqual(evidence.claim_frame.original, claim)

    def test_evidence_has_quotes(self) -> None:
        """Test that evidence includes quote-level evidence."""
        claim = "Python supports async programming"
        item = make_search_item(
            title="Python Async Guide",
            url="https://docs.python.org/async",
            snippet="Python supports async programming. The asyncio library provides async support.",
            content="Python supports async programming. The asyncio library provides async support. This is confirmed by official documentation.",
        )
        evidence = classify_evidence(claim, item, "discovery")
        self.assertGreater(len(evidence.quotes), 0)
        for quote in evidence.quotes:
            self.assertIsInstance(quote, EvidenceQuote)
            self.assertIn(quote.stance, [EvidenceStance.support, EvidenceStance.neutral, EvidenceStance.contradict])


class VerdictDecisionTests(unittest.TestCase):
    """Tests for verdict decision functionality."""

    def test_supported_verdict(self) -> None:
        """Test supported verdict with strong evidence."""
        claim = "Python supports async programming"
        items = [
            make_search_item(
                title="Python Async Guide",
                url="https://docs.python.org/async",
                snippet="Python supports async programming with asyncio",
            ),
            make_search_item(
                title="Asyncio Documentation",
                url="https://docs.python.org/library/asyncio",
                snippet="asyncio is Python's standard library for async programming",
            ),
        ]
        evidence = [classify_evidence(claim, item, "discovery") for item in items]
        verdict, confidence, reason, metadata = decide_verdict(evidence)
        self.assertEqual(verdict, Verdict.supported)
        self.assertGreater(confidence, 0.4)
        self.assertIsNotNone(metadata)
        self.assertGreater(metadata.evidence_count, 0)

    def test_contradicted_verdict(self) -> None:
        """Test contradicted verdict."""
        claim = "Python supports static typing"
        items = [
            make_search_item(
                title="Python Typing False",
                url="https://example.com/article",
                snippet="The claim that Python supports static typing is false. Python is dynamically typed.",
            ),
        ]
        evidence = [classify_evidence(claim, item, "contradiction") for item in items]
        verdict, confidence, reason, metadata = decide_verdict(evidence)
        self.assertEqual(verdict, Verdict.contradicted)

    def test_insufficient_verdict(self) -> None:
        """Test insufficient verdict with no relevant evidence."""
        claim = "Aliens exist on Mars"
        items = [
            make_search_item(
                title="Mars Exploration",
                url="https://example.com/mars",
                snippet="Mars is a planet in our solar system.",
            ),
        ]
        evidence = [classify_evidence(claim, item, "discovery") for item in items]
        verdict, confidence, reason, metadata = decide_verdict(evidence)
        self.assertEqual(verdict, Verdict.insufficient)
        self.assertIn("low_evidence_count", metadata.uncertainty_flags)

    def test_conflicting_verdict(self) -> None:
        """Test conflicting verdict with mixed evidence."""
        claim = "Coffee is healthy"
        items = [
            make_search_item(
                title="Coffee Health Benefits",
                url="https://health.gov/coffee",
                snippet="Studies show coffee has health benefits including reduced risk of certain diseases.",
            ),
            make_search_item(
                title="Coffee Health Risks Debunked",
                url="https://health.gov/risks",
                snippet="The claim that coffee is healthy is false. Research shows coffee increases health risks.",
            ),
        ]
        evidence = [classify_evidence(claim, item, "discovery") for item in items]
        verdict, confidence, reason, metadata = decide_verdict(evidence)
        self.assertEqual(verdict, Verdict.conflicting)
        self.assertIn("conflicting_evidence", metadata.uncertainty_flags)

    def test_verdict_metadata_has_source_diversity(self) -> None:
        """Test verdict metadata includes source diversity."""
        claim = "Python supports async"
        items = [
            make_search_item(
                title="Python Docs",
                url="https://docs.python.org/async",
                snippet="Python supports async",
            ),
            make_search_item(
                title="Reddit Discussion",
                url="https://reddit.com/python",
                snippet="Python async discussion",
            ),
        ]
        evidence = [classify_evidence(claim, item, "discovery") for item in items]
        verdict, confidence, reason, metadata = decide_verdict(evidence)
        self.assertGreater(metadata.source_diversity, 0)

    def test_verdict_metadata_has_calibration_factors(self) -> None:
        """Test verdict metadata includes calibration factors."""
        claim = "Python supports async"
        items = [
            make_search_item(
                title="Python Docs",
                url="https://docs.python.org/async",
                snippet="Python supports async programming",
            ),
        ]
        evidence = [classify_evidence(claim, item, "discovery") for item in items]
        verdict, confidence, reason, metadata = decide_verdict(evidence)
        self.assertIn("strong_source_boost", metadata.calibration_factors)
        self.assertIn("source_diversity_factor", metadata.calibration_factors)


class QuoteLevelEvidenceTests(unittest.TestCase):
    """Tests for quote-level evidence stance detection."""

    def test_quote_support_stance(self) -> None:
        """Test quote with support stance."""
        claim = "Python supports async"
        item = make_search_item(
            title="Python Async",
            url="https://docs.python.org/async",
            snippet="Python supports async programming. This is confirmed by official documentation.",
        )
        evidence = classify_evidence(claim, item, "discovery")
        support_quotes = [q for q in evidence.quotes if q.stance == EvidenceStance.support]
        self.assertGreater(len(support_quotes), 0)

    def test_quote_contradict_stance(self) -> None:
        """Test quote with contradict stance."""
        claim = "Python supports static typing"
        item = make_search_item(
            title="Python Typing",
            url="https://example.com/article",
            snippet="The claim is false. Python does not support static typing.",
        )
        evidence = classify_evidence(claim, item, "contradiction")
        contradict_quotes = [q for q in evidence.quotes if q.stance == EvidenceStance.contradict]
        self.assertGreater(len(contradict_quotes), 0)

    def test_quote_has_relevance_score(self) -> None:
        """Test quote has relevance score."""
        claim = "Python supports async"
        item = make_search_item(
            title="Python Async",
            url="https://docs.python.org/async",
            snippet="Python supports async programming.",
        )
        evidence = classify_evidence(claim, item, "discovery")
        for quote in evidence.quotes:
            self.assertGreater(quote.relevance_score, 0)
            self.assertLessEqual(quote.relevance_score, 1.0)


class BackwardCompatibilityTests(unittest.TestCase):
    """Tests for backward compatibility with existing behavior."""

    def test_verify_evidence_has_quote_field(self) -> None:
        """Test VerifyEvidence still has quote field."""
        claim = "Python supports async"
        item = make_search_item(
            title="Python Async",
            url="https://docs.python.org/async",
            snippet="Python supports async programming",
        )
        evidence = classify_evidence(claim, item, "discovery")
        self.assertIsNotNone(evidence.quote)
        self.assertIn("async", evidence.quote.lower())

    def test_verdict_values_match_expected(self) -> None:
        """Test verdict values match expected strings."""
        self.assertEqual(Verdict.supported.value, "supported")
        self.assertEqual(Verdict.contradicted.value, "contradicted")
        self.assertEqual(Verdict.partially_true.value, "partially_true")
        self.assertEqual(Verdict.insufficient.value, "insufficient")
        self.assertEqual(Verdict.conflicting.value, "conflicting")

    def test_evidence_stance_values_match_expected(self) -> None:
        """Test evidence stance values match expected strings."""
        self.assertEqual(EvidenceStance.support.value, "support")
        self.assertEqual(EvidenceStance.contradict.value, "contradict")
        self.assertEqual(EvidenceStance.neutral.value, "neutral")


if __name__ == "__main__":
    unittest.main()