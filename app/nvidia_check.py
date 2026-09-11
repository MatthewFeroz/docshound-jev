"""Run a small live embedding check: python -m app.nvidia_check."""

import asyncio
import json

import httpx

from app.config import get_settings
from app.state import GapCluster
from app.tools.docs_discovery import DocumentPage
from app.tools.docs_retrieval import rank_chunks_for_gaps
from app.tools.nvidia_embed import retrieve_semantic


async def main() -> int:
    settings = get_settings()
    if not settings.nvidia_api_key or not settings.nvidia_api_key.get_secret_value().strip():
        print("Set NVIDIA_API_KEY in .env or your environment, then rerun this command.")
        return 2
    cluster = GapCluster(
        name="Duplicate downloads",
        summary="Simultaneous requests trigger duplicate downloads.",
        recurring_question="How can simultaneous requests avoid duplicate downloads?",
        issue_numbers=[1],
        severity="medium",
        confidence=0.8,
    )
    pages = [
        DocumentPage(
            title="Cache behavior",
            url="https://example.com/docs/cache",
            text="In-flight operations are coalesced by cache key. Only one fetch runs per key.",
        ),
        DocumentPage(
            title="Appearance",
            url="https://example.com/docs/themes",
            text="Select a color palette and choose between dark and light editor themes.",
        ),
    ]
    lexical = rank_chunks_for_gaps([cluster], pages, per_gap=20, dedupe_pages=False)
    async with httpx.AsyncClient() as client:
        result = await retrieve_semantic(client, [cluster], pages, lexical, settings)
    print(json.dumps(result.details(), indent=2))
    if result.status != "hybrid":
        return 1
    if result.candidates[0][0].page.url != pages[0].url:
        print("The request succeeded, but the expected evidence did not rank first.")
        return 1
    print("Live embedding check passed. This two-passage fixture is not a quality benchmark.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
