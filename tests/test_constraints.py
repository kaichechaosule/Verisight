"""Offline tests for SearchConstraints and gap-driven follow-ups."""
import unittest

from verisight.schema import (
    SearchConstraints,
    SearchItem,
)
from verisight.rank import (
    apply_constraints,
    extract_domain,
    extract_date_from_text,
    matches_source_profile,
)
from verisight.deep import (
    detect_gaps,
    generate_gap_driven_followups,
    generate_follow_up_queries,
)


def make_search_item(
    title: str,
    url: str,
    snippet: str,
    provider: str = "test",
    published_at: str | None = None,
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
        published_at=published_at,
    )


class DomainExtractionTests(unittest.TestCase):
    """Tests for domain extraction functionality."""

    def test_extract_domain_from_url(self) -> None:
        """Test extracting domain from URL."""
        domain = extract_domain("https://docs.python.org/library")
        self.assertEqual(domain, "docs.python.org")

    def test_extract_domain_from_simple_url(self) -> None:
        """Test extracting domain from simple URL."""
        domain = extract_domain("https://example.com/page")
        self.assertEqual(domain, "example.com")

    def test_extract_domain_lowercase(self) -> None:
        """Test domain is lowercase."""
        domain = extract_domain("https://Docs.Python.org/library")
        self.assertEqual(domain, "docs.python.org")


class DateExtractionTests(unittest.TestCase):
    """Tests for date extraction functionality."""

    def test_extract_iso_date(self) -> None:
        """Test extracting ISO format date."""
        from datetime import datetime
        date = extract_date_from_text("Published on 2024-01-15")
        self.assertEqual(date, datetime(2024, 1, 15))

    def test_extract_year_only(self) -> None:
        """Test extracting year only."""
        from datetime import datetime
        date = extract_date_from_text("In 2023 we saw...")
        self.assertEqual(date, datetime(2023, 1, 1))

    def test_extract_date_none(self) -> None:
        """Test no date found."""
        date = extract_date_from_text("No date here")
        self.assertIsNone(date)

    def test_extract_date_empty_text(self) -> None:
        """Test empty text returns None."""
        date = extract_date_from_text("")
        self.assertIsNone(date)


class SearchConstraintsTests(unittest.TestCase):
    """Tests for SearchConstraints filtering."""

    def test_allowed_domains_filter(self) -> None:
        """Test filtering by allowed domains."""
        items = [
            make_search_item("Python Docs", "https://docs.python.org/async", "Python async"),
            make_search_item("Random Blog", "https://blog.example.com/post", "Blog post"),
        ]
        constraints = SearchConstraints(allowed_domains=["python.org"])
        filtered = apply_constraints(items, constraints)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].url, "https://docs.python.org/async")

    def test_allowed_domains_subdomain(self) -> None:
        """Test allowed domains matches subdomains."""
        items = [
            make_search_item("Python Docs", "https://docs.python.org/async", "Python async"),
            make_search_item("Python Main", "https://python.org/main", "Python main"),
        ]
        constraints = SearchConstraints(allowed_domains=["python.org"])
        filtered = apply_constraints(items, constraints)
        self.assertEqual(len(filtered), 2)

    def test_excluded_domains_filter(self) -> None:
        """Test filtering by excluded domains."""
        items = [
            make_search_item("Python Docs", "https://docs.python.org/async", "Python async"),
            make_search_item("Reddit Post", "https://reddit.com/python", "Reddit discussion"),
        ]
        constraints = SearchConstraints(excluded_domains=["reddit.com"])
        filtered = apply_constraints(items, constraints)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].url, "https://docs.python.org/async")

    def test_excluded_domains_subdomain(self) -> None:
        """Test excluded domains matches subdomains."""
        items = [
            make_search_item("Reddit Post", "https://www.reddit.com/python", "Reddit"),
            make_search_item("Old Reddit", "https://old.reddit.com/python", "Old Reddit"),
        ]
        constraints = SearchConstraints(excluded_domains=["reddit.com"])
        filtered = apply_constraints(items, constraints)
        self.assertEqual(len(filtered), 0)

    def test_official_source_profile_filters_community_sources(self) -> None:
        """Test official source profile keeps official/docs sources and filters forums."""
        items = [
            make_search_item("Python Docs", "https://docs.python.org/async", "Official docs"),
            make_search_item("Reddit Thread", "https://reddit.com/r/python/comments/1", "User discussion"),
        ]
        constraints = SearchConstraints(source_profile="official")
        filtered = apply_constraints(items, constraints)
        self.assertEqual([item.url for item in filtered], ["https://docs.python.org/async"])

    def test_community_source_profile_keeps_forum_sources(self) -> None:
        """Test community source profile keeps Reddit and StackOverflow-like sources."""
        items = [
            make_search_item("Python Docs", "https://docs.python.org/async", "Official docs"),
            make_search_item("StackOverflow", "https://stackoverflow.com/questions/1", "User debugging"),
            make_search_item("Reddit", "https://reddit.com/r/python/comments/1", "User discussion"),
        ]
        constraints = SearchConstraints(source_profile="community")
        filtered = apply_constraints(items, constraints)
        self.assertEqual(
            [item.url for item in filtered],
            ["https://stackoverflow.com/questions/1", "https://reddit.com/r/python/comments/1"],
        )

    def test_balanced_source_profile_keeps_all_sources(self) -> None:
        """Test balanced source profile does not filter by source type."""
        item = make_search_item("Reddit", "https://reddit.com/r/python/comments/1", "User discussion")
        self.assertTrue(matches_source_profile(item, "balanced"))

    def test_official_source_profile_does_not_treat_github_issues_as_official(self) -> None:
        """Test GitHub issues are not treated as official docs by the official profile."""
        issue = make_search_item("Issue", "https://github.com/org/repo/issues/1", "Bug discussion")
        release = make_search_item("Release", "https://github.com/org/repo/releases/tag/v1", "Official release")
        self.assertFalse(matches_source_profile(issue, "official"))
        self.assertTrue(matches_source_profile(release, "official"))

    def test_from_date_filter(self) -> None:
        """Test filtering by from_date."""
        items = [
            make_search_item("Old Article", "https://example.com/old", "From 2020", published_at="2020-01-01"),
            make_search_item("New Article", "https://example.com/new", "From 2024", published_at="2024-01-01"),
        ]
        constraints = SearchConstraints(from_date="2023-01-01")
        filtered = apply_constraints(items, constraints)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].url, "https://example.com/new")

    def test_to_date_filter(self) -> None:
        """Test filtering by to_date."""
        items = [
            make_search_item("Old Article", "https://example.com/old", "From 2020", published_at="2020-01-01"),
            make_search_item("New Article", "https://example.com/new", "From 2024", published_at="2024-01-01"),
        ]
        constraints = SearchConstraints(to_date="2023-01-01")
        filtered = apply_constraints(items, constraints)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].url, "https://example.com/old")

    def test_no_constraints_returns_all(self) -> None:
        """Test no constraints returns all items."""
        items = [
            make_search_item("Item 1", "https://example.com/1", "Content 1"),
            make_search_item("Item 2", "https://example.com/2", "Content 2"),
        ]
        filtered = apply_constraints(items, None)
        self.assertEqual(len(filtered), 2)

    def test_combined_constraints(self) -> None:
        """Test combined domain and date constraints."""
        items = [
            make_search_item("Python 2020", "https://docs.python.org/old", "2020", published_at="2020-01-01"),
            make_search_item("Python 2024", "https://docs.python.org/new", "2024", published_at="2024-01-01"),
            make_search_item("Reddit 2024", "https://reddit.com/new", "2024", published_at="2024-01-01"),
        ]
        constraints = SearchConstraints(
            allowed_domains=["python.org"],
            from_date="2023-01-01",
        )
        filtered = apply_constraints(items, constraints)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].url, "https://docs.python.org/new")


class GapDetectionTests(unittest.TestCase):
    """Tests for gap detection functionality."""

    def test_detect_missing_official_source(self) -> None:
        """Test detecting missing official source."""
        items = [
            make_search_item("Blog Post", "https://blog.example.com/post", "Blog content"),
        ]
        gaps = detect_gaps("Python async", items, [])
        self.assertTrue(gaps["missing_official_source"])

    def test_detect_has_official_source(self) -> None:
        """Test detecting official source present."""
        items = [
            make_search_item("Python Docs", "https://docs.python.org/async", "Official docs"),
        ]
        gaps = detect_gaps("Python async", items, [])
        self.assertFalse(gaps["missing_official_source"])

    def test_detect_missing_contradiction(self) -> None:
        """Test detecting missing contradiction evidence."""
        items = [
            make_search_item("Support Article", "https://example.com/support", "Python supports async"),
        ]
        gaps = detect_gaps("Python async", items, [])
        self.assertTrue(gaps["missing_contradiction"])

    def test_detect_has_contradiction(self) -> None:
        """Test detecting contradiction evidence present."""
        items = [
            make_search_item("Correction", "https://example.com/correction", "This claim is false"),
        ]
        gaps = detect_gaps("Python async", items, [])
        self.assertFalse(gaps["missing_contradiction"])

    def test_detect_temporal_query(self) -> None:
        """Test detecting temporal query."""
        items = []
        gaps = detect_gaps("Python will support feature in 2025", items, [])
        self.assertTrue(gaps["temporal_query"])

    def test_detect_non_temporal_query(self) -> None:
        """Test detecting non-temporal query."""
        items = []
        gaps = detect_gaps("Python supports async", items, [])
        self.assertFalse(gaps["temporal_query"])

    def test_detect_numeric_signal(self) -> None:
        """Test detecting numeric signal."""
        items = []
        gaps = detect_gaps("50% of users prefer Python", items, [])
        self.assertTrue(gaps["exact_numeric_signal"])

    def test_detect_low_source_diversity(self) -> None:
        """Test detecting low source diversity."""
        items = [
            make_search_item("Item 1", "https://example.com/1", "Content"),
            make_search_item("Item 2", "https://example.com/2", "Content"),
        ]
        gaps = detect_gaps("Python async", items, [])
        self.assertTrue(gaps["low_source_diversity"])

    def test_detect_high_source_diversity(self) -> None:
        """Test detecting high source diversity."""
        items = [
            make_search_item("Item 1", "https://docs.python.org/1", "Content"),
            make_search_item("Item 2", "https://reddit.com/2", "Content"),
            make_search_item("Item 3", "https://blog.example.com/3", "Content"),
        ]
        gaps = detect_gaps("Python async", items, [])
        self.assertFalse(gaps["low_source_diversity"])

    def test_detect_limited_evidence(self) -> None:
        """Test detecting limited evidence."""
        items = [
            make_search_item("Item 1", "https://example.com/1", "Content"),
        ]
        gaps = detect_gaps("Python async", items, [])
        self.assertTrue(gaps["limited_evidence"])


class GapDrivenFollowupTests(unittest.TestCase):
    """Tests for gap-driven follow-up query generation."""

    def test_generate_official_source_followup(self) -> None:
        """Test generating follow-up for missing official source."""
        items = [
            make_search_item("Blog", "https://blog.example.com/post", "Content"),
        ]
        gaps = {"missing_official_source": True}
        followups = generate_gap_driven_followups("Python async", items, [], gaps, set(), 3)
        self.assertTrue(any("official" in q.lower() or "docs" in q.lower() for q in followups))

    def test_generate_contradiction_followup(self) -> None:
        """Test generating follow-up for missing contradiction."""
        items = [
            make_search_item("Support", "https://example.com/support", "Supports"),
        ]
        gaps = {"missing_contradiction": True}
        followups = generate_gap_driven_followups("Python async", items, [], gaps, set(), 3)
        self.assertTrue(any("false" in q.lower() or "controversy" in q.lower() for q in followups))

    def test_generate_temporal_followup(self) -> None:
        """Test generating follow-up for temporal query."""
        items = []
        gaps = {"temporal_query": True}
        followups = generate_gap_driven_followups("Python in 2025", items, [], gaps, set(), 3)
        self.assertTrue(any("2025" in q or "latest" in q.lower() or "recent" in q.lower() for q in followups))

    def test_generate_temporal_followup_uses_date_constraints(self) -> None:
        """Test temporal follow-ups include explicit date constraints when provided."""
        gaps = {"temporal_query": True}
        constraints = SearchConstraints(from_date="2024-01-01", to_date="2024-12-31")
        followups = generate_gap_driven_followups("Python release", [], [], gaps, set(), 5, constraints)
        self.assertIn("Python release after:2024-01-01", followups)
        self.assertIn("Python release before:2024-12-31", followups)

    def test_generate_official_followup_uses_allowed_domains(self) -> None:
        """Test missing official source follow-ups prioritize allowed domains."""
        gaps = {"missing_official_source": True}
        constraints = SearchConstraints(allowed_domains=["docs.python.org"])
        followups = generate_gap_driven_followups("Python async", [], [], gaps, set(), 3, constraints)
        self.assertEqual(followups[0], "site:docs.python.org Python async")

    def test_generate_numeric_followup(self) -> None:
        """Test generating follow-up for numeric signal."""
        items = []
        gaps = {"exact_numeric_signal": True}
        followups = generate_gap_driven_followups("50% users", items, [], gaps, set(), 3)
        self.assertTrue(any("statistics" in q.lower() or "data" in q.lower() or "report" in q.lower() for q in followups))

    def test_followups_deduplicated(self) -> None:
        """Test follow-ups are deduplicated."""
        items = []
        gaps = {"missing_official_source": True}
        explored = {"python async official documentation"}
        followups = generate_gap_driven_followups("Python async", items, [], gaps, explored, 5)
        # Should not include the already explored query
        self.assertFalse(any(q.lower() == "python async official documentation" for q in followups))

    def test_followups_limit_respected(self) -> None:
        """Test follow-ups limit is respected."""
        items = []
        gaps = {
            "missing_official_source": True,
            "missing_contradiction": True,
            "temporal_query": True,
        }
        followups = generate_gap_driven_followups("Python async", items, [], gaps, set(), 2)
        self.assertEqual(len(followups), 2)


class CombinedFollowupTests(unittest.TestCase):
    """Tests for combined follow-up query generation."""

    def test_combined_followups_includes_gap_driven(self) -> None:
        """Test combined follow-ups include gap-driven queries."""
        items = [
            make_search_item("Blog", "https://blog.example.com/post", "Content"),
        ]
        followups = generate_follow_up_queries("Python async", items, [], set(), 5)
        # Should include gap-driven follow-ups for missing official source
        self.assertTrue(len(followups) > 0)

    def test_combined_followups_deduplicated(self) -> None:
        """Test combined follow-ups are deduplicated."""
        items = [
            make_search_item("Docs", "https://docs.python.org/async", "Official docs"),
        ]
        explored = {"python async"}
        followups = generate_follow_up_queries("Python async", items, [], explored, 5)
        self.assertFalse(any(q.lower() == "python async" for q in followups))

    def test_combined_followups_use_constraints(self) -> None:
        """Test combined follow-ups pass constraints into gap-driven generation."""
        constraints = SearchConstraints(allowed_domains=["docs.python.org"])
        followups = generate_follow_up_queries("Python async", [], [], set(), 3, constraints)
        self.assertIn("site:docs.python.org Python async", followups)


class SearchConstraintsModelTests(unittest.TestCase):
    """Tests for SearchConstraints model."""

    def test_constraints_default_values(self) -> None:
        """Test SearchConstraints default values."""
        constraints = SearchConstraints()
        self.assertEqual(constraints.allowed_domains, [])
        self.assertEqual(constraints.excluded_domains, [])
        self.assertIsNone(constraints.from_date)
        self.assertIsNone(constraints.to_date)
        self.assertFalse(constraints.strict_mode)
        self.assertEqual(constraints.source_profile, "balanced")

    def test_constraints_with_values(self) -> None:
        """Test SearchConstraints with values."""
        constraints = SearchConstraints(
            allowed_domains=["python.org"],
            excluded_domains=["reddit.com"],
            from_date="2023-01-01",
            to_date="2024-01-01",
            strict_mode=True,
            source_profile="community",
        )
        self.assertEqual(constraints.allowed_domains, ["python.org"])
        self.assertEqual(constraints.excluded_domains, ["reddit.com"])
        self.assertEqual(constraints.from_date, "2023-01-01")
        self.assertEqual(constraints.to_date, "2024-01-01")
        self.assertTrue(constraints.strict_mode)
        self.assertEqual(constraints.source_profile, "community")


if __name__ == "__main__":
    unittest.main()
