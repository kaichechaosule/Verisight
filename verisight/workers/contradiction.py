from __future__ import annotations

from verisight.workers.base import WorkerPlan, normalize_text


class ContradictionWorker:
    name = "contradiction"
    purpose = "Look for corrections, deprecations, and evidence that may challenge the claim."

    def plan(self, text: str) -> WorkerPlan:
        normalized = normalize_text(text)
        return WorkerPlan(
            name=self.name,
            purpose=self.purpose,
            queries=[
                f"{normalized} false",
                f"{normalized} correction",
                f"{normalized} deprecated OR no longer",
                f"{normalized} controversy",
            ],
        )
