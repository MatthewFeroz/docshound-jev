import asyncio
import json
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.state import GapCluster, Issue, PullRequest, RunRequest
from app.tools.cluster import cluster_issues
from app.tools.github import research_pull_requests, research_repo
from app.tools.nvidia_embed import _embed


def github_item(number, *, merged=True):
    return {
        "number": number,
        "title": f"Configure feature {number}",
        "body": "Configuration guide",
        "html_url": f"https://github.com/acme/project/issues/{number}",
        "state": "closed",
        "labels": [],
        "comments": 0,
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "merged_at": "2026-09-01T00:00:00Z" if merged else None,
    }


def evidence(count):
    now = datetime.now(UTC)
    common = {
        "body": "Configuration instructions",
        "state": "closed",
        "created_at": now,
        "updated_at": now,
        "url": "https://github.com/acme/project/issues/1",
    }
    issues = [
        Issue(number=i, title=f"Question {i}", comments_count=0, **common)
        for i in range(1, count + 1)
    ]
    prs = [
        PullRequest(number=1000 + i, title=f"New feature {i}", merged_at=now, **common)
        for i in range(1, count + 1)
    ]
    return issues, prs


class ScanDepthTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_collectors_honor_50_and_100_after_filtering_pages(self):
        real_client = httpx.AsyncClient

        def handler(request):
            page = int(request.url.params["page"])
            if page == 1:
                items = [github_item(i, merged=False) for i in range(1, 101)]
                if request.url.path.endswith("/issues"):
                    for item in items:
                        item["pull_request"] = {}
            else:
                items = [github_item(i) for i in range(101, 201)] if page == 2 else []
            return httpx.Response(200, json=items)

        with patch(
            "app.tools.github.httpx.AsyncClient",
            side_effect=lambda **kwargs: real_client(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ):
            for limit in (50, 100):
                issues = await research_repo("acme/project", limit)
                prs = await research_pull_requests("acme/project", limit)
                self.assertEqual(len(issues), limit)
                self.assertEqual(len(prs), limit)
                self.assertEqual(prs[-1].number, 100 + limit)

    async def test_short_repository_returns_available_evidence(self):
        real_client = httpx.AsyncClient

        def handler(request):
            items = [github_item(1)] if request.url.params["page"] == "1" else []
            return httpx.Response(200, json=items)

        with patch(
            "app.tools.github.httpx.AsyncClient",
            side_effect=lambda **kwargs: real_client(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        ):
            self.assertEqual(len(await research_pull_requests("acme/project", 100)), 1)

    async def test_analysis_batches_include_every_collected_issue_and_pr(self):
        issues, prs = evidence(100)
        batches = []

        async def analyze(batch_issues, batch_prs, **kwargs):
            batches.append((batch_issues, batch_prs))
            return [
                GapCluster(
                    name=f"Gap {len(batches)}",
                    summary="Configuration",
                    recurring_question="How?",
                    issue_numbers=[batch_issues[-1].number],
                    severity="high",
                    confidence=0.9,
                )
            ]

        with (
            patch(
                "app.tools.cluster.llm_is_configured",
                return_value=True,
            ),
            patch("app.tools.cluster._cluster_with_llm", side_effect=analyze),
        ):
            result = await cluster_issues(issues, prs)
        self.assertEqual(
            [i.number for batch, _ in batches for i in batch], list(range(1, 101))
        )
        self.assertEqual(
            [p.number for _, batch in batches for p in batch], list(range(1001, 1101))
        )
        self.assertTrue(any(100 in c.issue_numbers for c in result))
        self.assertEqual(len(batches), 2)

    async def test_parallel_embedding_batches_preserve_order_and_bound_concurrency(
        self,
    ):
        active = peak = 0

        async def handler(request):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            body = json.loads(request.content)
            await asyncio.sleep(0.005 if body["input"][0] == "0" else 0.001)
            active -= 1
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": i, "embedding": [float(value) + 1, 1.0]}
                        for i, value in enumerate(body["input"])
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            vectors = await _embed(
                client,
                [str(i) for i in range(80)],
                "passage",
                Settings(_env_file=None, nvidia_api_key="test"),
            )
        self.assertEqual(len(vectors), 80)
        self.assertEqual(peak, 4)
        for i, vector in enumerate(vectors):
            self.assertAlmostEqual(vector[0] / vector[1], i + 1)

    def test_scan_budgets_are_independent_and_validated(self):
        request = RunRequest(
            repo="acme/project",
            limit=100,
            repo_docs_max_files=200,
            nvidia_embed_max_passages=2048,
        )
        self.assertEqual(request.limit, 100)
        for overrides in (
            {"limit": 101},
            {"repo_docs_max_files": 501},
            {"nvidia_embed_max_passages": 4097},
        ):
            with self.assertRaises(ValidationError):
                RunRequest(repo="acme/project", **overrides)


if __name__ == "__main__":
    unittest.main()
