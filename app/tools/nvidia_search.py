"""Optional NVIDIA retrieval layered over the existing documentation search."""

import httpx

from app.config import Settings
from app.state import GapCluster
from app.tools.docs_discovery import DocumentPage
from app.tools.docs_retrieval import RetrievedChunk, rank_chunks_for_gaps
from app.tools.nvidia_embed import retrieve_semantic, select_pages
from app.tools.nvidia_rerank import rerank_gap
from app.tracing import observe_operation


async def enhance_ranked_evidence(
    clusters: list[GapCluster],
    pages: list[DocumentPage],
    ranked: dict[int, list[RetrievedChunk]],
    settings: Settings,
    per_gap: int = 3,
) -> dict[int, list[RetrievedChunk]]:
    candidates = rank_chunks_for_gaps(
        clusters,
        pages,
        per_gap=settings.nvidia_rerank_candidates,
        dedupe_pages=False,
    )
    async with httpx.AsyncClient() as client:
        if settings.nvidia_embed_enabled:
            result = await observe_operation(
                "retrieve_semantic_docs",
                retrieve_semantic,
                client,
                clusters,
                pages,
                candidates,
                settings,
                limit=settings.nvidia_rerank_candidates,
                input_details={
                    "model": settings.nvidia_embed_model,
                    "page_count": len(pages),
                },
                output_summary=lambda value: f"{value.status}: {value.reason}",
                output_details=lambda value: value.details(),
                trace_outputs=lambda value: value.details(),
            )
            if result.status == "hybrid":
                candidates = result.candidates
                ranked = {
                    i: select_pages(chunks, limit=per_gap) for i, chunks in candidates.items()
                }
        if settings.nvidia_rerank_enabled:
            for index, cluster in enumerate(clusters):
                result = await observe_operation(
                    "rerank_docs_for_gap",
                    rerank_gap,
                    client,
                    cluster,
                    candidates.get(index, []),
                    ranked.get(index, []),
                    settings,
                    per_gap=per_gap,
                    input_summary=cluster.name,
                    output_summary=lambda value: f"{value.status}: {value.reason}",
                    output_details=lambda value: value.details(),
                    trace_outputs=lambda value: value.details(),
                )
                ranked[index] = result.chunks
    return ranked
