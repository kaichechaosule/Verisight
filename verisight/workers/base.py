from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WorkerPlan:
    name: str
    purpose: str
    queries: list[str]


class SearchWorker(Protocol):
    name: str
    purpose: str

    def plan(self, text: str) -> WorkerPlan:
        raise NotImplementedError


def normalize_text(value: str) -> str:
    return " ".join(value.split())
