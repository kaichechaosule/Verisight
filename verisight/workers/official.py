from __future__ import annotations

from verisight.workers.base import WorkerPlan, normalize_text


class OfficialSourceWorker:
    name = "official"
    purpose = "Prioritize official documentation, code hosts, and primary sources."

    def plan(self, text: str) -> WorkerPlan:
        normalized = normalize_text(text)
        return WorkerPlan(
            name=self.name,
            purpose=self.purpose,
            queries=[f"{normalized} official", f"{normalized} docs", f"{normalized} site:github.com"],
        )
