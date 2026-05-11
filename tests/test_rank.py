import unittest

from verisight.rank import dedupe_and_rank, normalize_url
from verisight.schema import SearchItem


class RankTests(unittest.TestCase):
    def test_normalize_url_removes_tracking_values(self) -> None:
        url = "https://example.com/page?utm_source=x&b=2&fbclid=y#section"

        self.assertEqual(normalize_url(url), "https://example.com/page?b=2")

    def test_dedupe_and_rank_merges_provider_duplicates(self) -> None:
        first = SearchItem(id="a", title="A", url="https://example.com?a=1&utm_source=x", provider="exa")
        second = SearchItem(id="b", title="B", url="https://example.com?a=1", provider="brave", score=0.9)

        ranked = dedupe_and_rank({"exa": [first], "brave": [second]}, 10)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].url, "https://example.com?a=1")
        self.assertEqual(ranked[0].metadata["providers"], ["brave", "exa"])


if __name__ == "__main__":
    unittest.main()
