from __future__ import annotations

from dataclasses import dataclass

from verisight.schema import SearchItem



@dataclass(frozen=True)
class ExtractionWorker:
    name: str = "extraction"
    purpose: str = "Extract top result pages so evidence classification can use page text, not only snippets."

    def plan_urls(self, results: list[SearchItem], limit: int) -> list[str]:
        if limit <= 0:
            return []
        urls: list[str] = []
        seen: set[str] = set()
        for result in results:
            if result.url in seen:
                continue
            seen.add(result.url)
            urls.append(result.url)
            if len(urls) >= limit:
                break
        return urls
