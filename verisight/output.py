from __future__ import annotations

import json
from typing import Any


def to_json_text(value: object, compact: bool = False) -> str:
    """Serialize a Pydantic model or plain object to JSON text."""
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    else:
        payload = value
    if compact and isinstance(payload, dict):
        payload = compact_payload(payload)
    return json.dumps(payload, ensure_ascii=True, indent=2)


def compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Reduce payload to key fields for compact output."""
    payload = dict(payload)
    if "results" in payload:
        payload["results"] = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": (r.get("snippet", "") or "")[:100],
            }
            for r in payload["results"][:5]
        ]
    if "citations" in payload:
        payload["citations"] = [
            {"url": c.get("url", ""), "title": c.get("title", "")}
            for c in payload["citations"][:3]
        ]
    if "diagnostics" in payload:
        payload["diagnostics"] = [
            {"provider": d.get("provider", ""), "ok": d.get("ok", False)}
            for d in payload["diagnostics"]
        ]
    if "iterations" in payload:
        payload["iterations"] = [
            {"iteration": i.get("iteration", 0), "queries": i.get("queries", [])}
            for i in payload["iterations"]
        ]
    payload.pop("evidence_graph", None)
    payload.pop("routing", None)
    if "supporting_evidence" in payload:
        payload["supporting_evidence"] = [
            {"url": e.get("url", ""), "stance": e.get("stance", ""), "score": e.get("score", 0)}
            for e in payload["supporting_evidence"][:3]
        ]
    if "contradicting_evidence" in payload:
        payload["contradicting_evidence"] = [
            {"url": e.get("url", ""), "stance": e.get("stance", ""), "score": e.get("score", 0)}
            for e in payload["contradicting_evidence"][:3]
        ]
    payload.pop("neutral_evidence", None)
    if "query_sets" in payload:
        payload["query_sets"] = [
            {"worker": q.get("worker", ""), "queries": q.get("queries", [])}
            for q in payload["query_sets"]
        ]
    claim_frame = payload.get("claim_frame")
    if claim_frame:
        payload["claim_frame"] = {
            "claim_type": claim_frame.get("claim_type", ""),
            "entities": claim_frame.get("entities", [])[:3],
            "negated": claim_frame.get("negated", False),
        }
    verdict_metadata = payload.get("verdict_metadata")
    if verdict_metadata:
        payload["verdict_metadata"] = {
            "evidence_count": verdict_metadata.get("evidence_count", 0),
            "source_diversity": verdict_metadata.get("source_diversity", 0),
            "uncertainty_flags": verdict_metadata.get("uncertainty_flags", []),
        }
    return payload
