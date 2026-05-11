from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    brave_api_key: str | None
    exa_api_key: str | None
    tavily_api_key: str | None
    jina_api_key: str | None
    timeout_seconds: float


def load_settings() -> Settings:
    return Settings(
        brave_api_key=os.getenv("BRAVE_API_KEY"),
        exa_api_key=os.getenv("EXA_API_KEY"),
        tavily_api_key=os.getenv("TAVILY_API_KEY"),
        jina_api_key=os.getenv("JINA_API_KEY"),
        timeout_seconds=float(os.getenv("WEBSEARCH_TIMEOUT_SECONDS", "15")),
    )
