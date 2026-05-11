import unittest

from verisight.providers.base import ProviderConfig
from verisight.providers.duckduckgo import DuckDuckGoProvider


class DuckDuckGoProviderTests(unittest.TestCase):
    def test_duckduckgo_provider_is_keyless_search_provider(self) -> None:
        provider = DuckDuckGoProvider(ProviderConfig(api_key=None, timeout_seconds=15))

        self.assertTrue(provider.available())
        self.assertTrue(provider.supports_search())
        self.assertFalse(provider.supports_extract())


if __name__ == "__main__":
    unittest.main()
