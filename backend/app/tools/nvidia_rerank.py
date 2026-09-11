"""Bounded NVIDIA reranking, preserving the original evidence and lexical scores."""

import math
from dataclasses import dataclass, replace

import httpx

from app.config import Settings
from app.state import GapCluster
from app.tools.docs_retrieval import RetrievedChunk
from app.usage import track_model_call


@dataclass
class RerankResult:
    chunks: list[RetrievedChunk]
    status: str
    reason: str
    model: str
    candidate_count: int

    def details(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason,
            "model": self.model,
            "candidate_count": self.candidate_count,
            "selected_count": len(self.chunks),
            "sources": [
                {
                    "url": chunk.page.url,
                    "lexical_score": chunk.score,
                    "rerank_score": chunk.rerank_score,
                }
                for chunk in self.chunks
            ],
        }


async def rerank_gap(
    client: httpx.AsyncClient,
    cluster: GapCluster,
    candidates: list[RetrievedChunk],
    fallback: list[RetrievedChunk],
    settings: Settings,
    per_gap: int = 3,
) -> RerankResult:
    """Use only submitted passages; invalid or unavailable responses retain baseline results."""
    candidates = candidates[: settings.nvidia_rerank_candidates]

    def result(chunks: list[RetrievedChunk], status: str, reason: str) -> RerankResult:
        return RerankResult(
            chunks, status, reason, settings.nvidia_rerank_model, len(candidates)
        )

    if not candidates:
        return result(fallback, "skipped", "No matching candidate passages")
    if (
        not settings.nvidia_api_key
        or not settings.nvidia_api_key.get_secret_value().strip()
    ):
        return result(fallback, "fallback", "NVIDIA_API_KEY is not configured")

    query = "\n".join([cluster.recurring_question, cluster.name, cluster.summary])[
        :3000
    ]
    try:
        with track_model_call(
            "nvidia", settings.nvidia_rerank_model, "reranking"
        ) as usage:
            response = await client.post(
                settings.nvidia_rerank_url,
                headers={
                    "Authorization": f"Bearer {settings.nvidia_api_key.get_secret_value()}",
                    "Accept": "application/json",
                },
                json={
                    "model": settings.nvidia_rerank_model,
                    "query": {"text": query},
                    "passages": [
                        {"text": f"{chunk.page.title[:300]}\n{chunk.text}"}
                        for chunk in candidates
                    ],
                    "truncate": "END",
                },
                timeout=settings.nvidia_rerank_timeout_seconds,
                follow_redirects=False,
            )
            response.raise_for_status()
            payload = response.json()
            usage.report(payload.get("usage") if isinstance(payload, dict) else None)
            ranked = _validated_ranking(payload, candidates)
    except httpx.HTTPStatusError as exc:
        # Do not publish response bodies or exception text: they may echo credentials.
        return result(fallback, "fallback", f"NVIDIA HTTP {exc.response.status_code}")
    except httpx.RequestError:
        return result(fallback, "fallback", "NVIDIA request failed or timed out")
    except ValueError, TypeError, KeyError:
        return result(fallback, "fallback", "Invalid NVIDIA ranking response")

    selected: list[RetrievedChunk] = []
    seen: set[str] = set()
    for chunk in ranked:
        if chunk.page.url not in seen:
            selected.append(chunk)
            seen.add(chunk.page.url)
        if len(selected) == per_gap:
            break
    return result(selected, "reranked", "NVIDIA ranked the candidate passages")


def _validated_ranking(
    payload: object, candidates: list[RetrievedChunk]
) -> list[RetrievedChunk]:
    if not isinstance(payload, dict) or not isinstance(payload.get("rankings"), list):
        raise ValueError("Expected rankings")
    rows = payload["rankings"]
    if len(rows) != len(candidates):
        raise ValueError("Incomplete rankings")
    seen: set[int] = set()
    ranked: list[RetrievedChunk] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid ranking row")
        index, score = row.get("index"), row.get("logit")
        if (
            type(index) is not int
            or index not in range(len(candidates))
            or index in seen
        ):
            raise ValueError("Invalid ranking index")
        if type(score) not in (int, float) or not math.isfinite(score):
            raise ValueError("Invalid ranking score")
        seen.add(index)
        ranked.append(replace(candidates[index], rerank_score=float(score)))
    # Logits can be negative. They are ordering signals, not calibrated confidence.
    return sorted(ranked, key=lambda chunk: chunk.rerank_score, reverse=True)
