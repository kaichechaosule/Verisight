from __future__ import annotations

from verisight.workers.base import WorkerPlan, normalize_text


class DiscoveryWorker:
    name = "discovery"
    purpose = "Find broad relevant sources and initial coverage."

    def plan(self, text: str) -> WorkerPlan:
        normalized = normalize_text(text)
        return WorkerPlan(
            name=self.name,
            purpose=self.purpose,
            queries=[normalized, f"{normalized} source"],
        )
