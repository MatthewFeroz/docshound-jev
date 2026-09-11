import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.config import Settings
from app.state import GapCluster
from app.tools.docs import search_official_docs
from app.tools.docs_discovery import DocumentPage
from app.tools.docs_retrieval import rank_chunks_for_gaps, source_confidence
from app.tools.nvidia_embed import _CACHE, retrieve_semantic, select_pages
from app.tools.nvidia_rerank import rerank_gap


def gap():
    return GapCluster(
        name="Duplicate downloads",
        summary="Simultaneous requests trigger duplicate downloads.",
        recurring_question="Can simultaneous requests avoid duplicate downloads?",
        issue_numbers=[1],
        severity="medium",
        confidence=0.8,
    )


def pages():
    return [
        DocumentPage(
            title="Downloads",
            url="https://example.com/docs/downloads",
            text="Duplicate downloads and simultaneous requests appear in the activity log. " * 3,
        ),
        DocumentPage(
            title="Coalescing",
            url="https://example.com/docs/coalescing",
            text="In-flight operations are coalesced by cache key. Only one fetch runs per key.",
        ),
    ]


def settings(**overrides):
    return Settings(_env_file=None, nvidia_api_key="test-secret", **overrides)


def embedding_handler(request):
    body = json.loads(request.content)
    vectors = []
    for index, text in enumerate(body["input"]):
        relevant = body["input_type"] == "query" or "coalesced" in text
        vectors.append({"index": index, "embedding": [1.0, 0.0] if relevant else [0.0, 1.0]})
    # Response order is deliberately different from input order.
    return httpx.Response(200, json={"data": list(reversed(vectors))})


class SemanticTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _CACHE.clear()

    async def run_search(self, handler=embedding_handler, config=None):
        docs = pages()
        lexical = rank_chunks_for_gaps([gap()], docs, per_gap=20, dedupe_pages=False)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await retrieve_semantic(client, [gap()], docs, lexical, config or settings())

    async def test_semantic_search_adds_evidence_with_no_keyword_overlap(self):
        lexical = rank_chunks_for_gaps([gap()], pages())
        self.assertEqual([chunk.page.url for chunk in lexical[0]], [pages()[0].url])
        result = await self.run_search()
        self.assertEqual(result.status, "hybrid")
        sources = {chunk.page.url: chunk for chunk in result.candidates[0]}
        self.assertIn(pages()[1].url, sources)
        semantic = sources[pages()[1].url]
        self.assertEqual(semantic.semantic_score, 1)
        self.assertEqual(semantic.score, 0)
        self.assertEqual(semantic.matched_terms, ())
        self.assertLess(source_confidence(semantic), 1)

    async def test_correct_input_types_auth_cache_and_model_isolation(self):
        requests = []

        def handler(request):
            requests.append(json.loads(request.content))
            self.assertEqual(request.headers["authorization"], "Bearer test-secret")
            return embedding_handler(request)

        first = await self.run_search(handler)
        second = await self.run_search(handler)
        third = await self.run_search(handler, settings(nvidia_embed_model="different-model"))
        self.assertEqual(first.cache_hits, 0)
        self.assertEqual(second.cache_hits, 2)
        self.assertEqual(third.cache_hits, 0)
        self.assertEqual(
            [body["input_type"] for body in requests],
            ["passage", "query", "query", "passage", "query"],
        )

    async def test_invalid_responses_fall_back_without_losing_keyword_results(self):
        payloads = [
            {},
            {"data": []},
            {"data": [{"index": 0, "embedding": [0, 0]}]},
            {"data": [{"index": -1, "embedding": [1, 0]}]},
            {"data": [{"index": True, "embedding": [1, 0]}]},
            {"data": [{"index": 0, "embedding": [1, 0]}] * 2},
            {"data": [{"index": 0, "embedding": ["secret", 0]}]},
            {
                "data": [
                    {"index": 0, "embedding": [1, 0]},
                    {"index": 1, "embedding": [1]},
                ]
            },
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                _CACHE.clear()
                result = await self.run_search(
                    lambda request, p=payload: httpx.Response(200, json=p)
                )
                self.assertEqual(result.status, "fallback")
                self.assertEqual([c.page.url for c in result.candidates[0]], [pages()[0].url])

    async def test_http_failure_and_timeout_are_explicit_and_sanitized(self):
        for status in (401, 429, 500):
            with self.subTest(status=status):
                result = await self.run_search(
                    lambda request, s=status: httpx.Response(s, text="test-secret")
                )
                self.assertEqual(result.status, "fallback")
                self.assertIn(str(status), result.reason)
                self.assertNotIn("test-secret", str(result.details()))

        def timeout(request):
            raise httpx.ReadTimeout("test-secret", request=request)

        result = await self.run_search(timeout)
        self.assertEqual(result.status, "fallback")
        self.assertNotIn("test-secret", result.reason)

    async def test_missing_key_and_empty_corpus_make_no_request(self):
        def unexpected(request):
            self.fail("Unexpected external request")

        async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as client:
            config = Settings(_env_file=None, nvidia_api_key=None)
            result = await retrieve_semantic(client, [gap()], pages(), {}, config)
            self.assertEqual(result.status, "fallback")
            result = await retrieve_semantic(client, [], pages(), {}, settings())
            self.assertEqual(result.status, "skipped")

    async def test_corpus_cap_and_cache_content_invalidation(self):
        result = await self.run_search(config=settings(nvidia_embed_max_passages=1))
        self.assertEqual(result.passage_count, 1)
        self.assertEqual(result.omitted_passages, 1)
        docs = pages()
        docs[0] = DocumentPage(title="Downloads", url=docs[0].url, text=docs[0].text + " Changed.")
        async with httpx.AsyncClient(transport=httpx.MockTransport(embedding_handler)) as client:
            changed = await retrieve_semantic(client, [gap()], docs, {}, settings())
        self.assertEqual(changed.cache_hits, 0)


class SearchIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def run_pipeline(self, config, fail=False):
        _CACHE.clear()
        requests = []

        async def post(client, url, **kwargs):
            request = httpx.Request("POST", url, json=kwargs["json"])
            requests.append(request)
            if fail:
                return httpx.Response(503, request=request, text="test-secret")
            if "passages" in kwargs["json"]:
                payload = {
                    "rankings": [
                        {"index": i, "logit": -1 if "coalesced" in p["text"] else -5}
                        for i, p in enumerate(kwargs["json"]["passages"])
                    ]
                }
                return httpx.Response(200, request=request, json=payload)
            response = embedding_handler(request)
            response.request = request
            return response

        with (
            patch("app.tools.docs.get_settings", return_value=config),
            patch("app.tools.docs.discover_docs_root", new=AsyncMock(return_value=None)),
            patch("app.tools.docs.fetch_document_pages", new=AsyncMock(return_value=pages())),
            patch("app.tools.docs.fetch_repository_readme", new=AsyncMock(return_value=None)),
            patch("httpx.AsyncClient.post", new=post),
        ):
            result = await search_official_docs("acme/product", None, [gap()])
        return result, requests

    async def test_disabled_features_preserve_existing_search_without_nvidia_calls(self):
        result, requests = await self.run_pipeline(settings(openai_api_key=None))
        self.assertEqual(requests, [])
        self.assertEqual([source.url for source in result], [pages()[0].url])
        self.assertEqual(result[0].coverage, "partially_covered")

    async def test_nvidia_evidence_reaches_coverage_and_preserves_reranked_order(self):
        result, requests = await self.run_pipeline(
            settings(openai_api_key=None, nvidia_embed_enabled=True, nvidia_rerank_enabled=True)
        )
        self.assertEqual(len(requests), 3)
        self.assertEqual([source.url for source in result], [pages()[1].url, pages()[0].url])
        self.assertTrue(all(source.gap_name == gap().name for source in result))
        self.assertTrue(all(source.coverage == "partially_covered" for source in result))

    async def test_provider_failures_preserve_existing_coverage_and_sources(self):
        baseline, _ = await self.run_pipeline(settings(openai_api_key=None))
        fallback, requests = await self.run_pipeline(
            settings(openai_api_key=None, nvidia_embed_enabled=True, nvidia_rerank_enabled=True),
            fail=True,
        )
        self.assertTrue(requests)
        self.assertEqual(fallback, baseline)


class RerankingTests(unittest.IsolatedAsyncioTestCase):
    async def test_reranking_preserves_evidence_scores_and_display_order(self):
        _CACHE.clear()
        async with httpx.AsyncClient(transport=httpx.MockTransport(embedding_handler)) as client:
            semantic = await retrieve_semantic(
                client,
                [gap()],
                pages(),
                rank_chunks_for_gaps([gap()], pages()),
                settings(),
            )
        candidates = semantic.candidates[0]

        def handler(request):
            body = json.loads(request.content)
            self.assertEqual(body["model"], settings().nvidia_rerank_model)
            return httpx.Response(
                200,
                json={
                    "rankings": [
                        {"index": i, "logit": -1 if "coalesced" in p["text"] else -5}
                        for i, p in enumerate(body["passages"])
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rerank_gap(
                client, gap(), candidates, select_pages(candidates), settings()
            )
        self.assertEqual(result.status, "reranked")
        self.assertEqual(result.chunks[0].page.url, pages()[1].url)
        self.assertEqual(result.chunks[0].score, 0)
        self.assertEqual(result.chunks[0].rerank_score, -1)

    async def test_invalid_ranking_and_http_failure_preserve_fallback(self):
        candidates = rank_chunks_for_gaps([gap()], pages())[0]
        responses = [
            httpx.Response(200, json={"rankings": []}),
            httpx.Response(200, json={"rankings": [{"index": 5, "logit": 1}]}),
            httpx.Response(200, json={"rankings": [{"index": 0, "logit": "bad"}]}),
            httpx.Response(429, text="test-secret"),
        ]
        for response in responses:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(lambda request, r=response: r)
            ) as client:
                result = await rerank_gap(client, gap(), candidates, candidates, settings())
            self.assertEqual(result.status, "fallback")
            self.assertEqual(result.chunks, candidates)
            self.assertNotIn("test-secret", str(result.details()))
