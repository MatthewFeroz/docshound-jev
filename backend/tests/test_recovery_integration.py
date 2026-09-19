import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.agent import run_agent
from app.config import Settings
from app.llm import complete_json
from app.main import app
from app.run_store import load_run
from app.state import RUNS, DocumentationSource, GapCluster, Issue, RunRequest
from app.tools.docs import RepositoryDocument, search_official_docs
from app.tools.docs_discovery import DocumentPage
from app.tools.docs_retrieval import rank_chunks_for_gaps
from app.tools.nvidia_embed import SemanticResult
from app.tools.repository_docs import RepositoryDocsResult
from app.usage import RunUsage, track_run_usage


def gap():
    return GapCluster(
        name="Configure retries",
        summary="How to configure retries?",
        recurring_question="How to configure retries?",
        issue_numbers=[1],
        severity="high",
        confidence=0.9,
    )


class RecoveryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_gateway_fallback_records_each_attempt_and_closes_client(self):
        create = AsyncMock(
            side_effect=[
                RuntimeError("temporary failure"),
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))
                    ],
                    model="gpt-5.6-luna",
                    usage={
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                    },
                ),
            ]
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            close=AsyncMock(),
        )
        settings = Settings(
            _env_file=None,
            merge_gateway_api_key="test",
            openai_api_key="unused",
            merge_gateway_primary_model="google/gemini-3.7-flash",
            merge_gateway_fallback_model="openai/gpt-5.6-luna",
        )
        usage = RunUsage()
        with (
            patch("app.llm.AsyncOpenAI", return_value=client),
            track_run_usage(usage, lambda: None),
        ):
            result = await complete_json(
                [{"role": "user", "content": "test"}],
                settings=settings,
                operation="coverage",
            )
        self.assertTrue(result.value["ok"])
        self.assertEqual(
            [call.request_status for call in usage.calls], ["failed", "succeeded"]
        )
        self.assertEqual(usage.summary()["total_tokens"], 12)
        self.assertEqual(usage.summary()["unpriced_calls"], 2)
        self.assertNotIn("api_key", usage.model_dump_json())
        client.close.assert_awaited_once()

    async def test_nvidia_evidence_enters_restored_coverage_with_independent_limits(
        self,
    ):
        settings = Settings(
            _env_file=None, nvidia_embed_enabled=True, nvidia_api_key="test"
        )
        page = DocumentPage(
            title="Retry policy",
            url="https://github.com/acme/docs/blob/" + "a" * 40 + "/guide/retries.md",
            text="Configure retries using the retry limit. Set retry_limit to control the maximum number of attempts.",
        )
        result = RepositoryDocsResult(pages=[page], revision="a" * 40)
        observed = {}

        async def semantic(client, clusters, pages, candidates, configured, **kwargs):
            observed["settings"] = configured
            return SemanticResult(
                candidates=rank_chunks_for_gaps(clusters, pages),
                status="hybrid",
                reason="semantic evidence",
                model=configured.nvidia_embed_model,
            )

        with (
            patch("app.tools.docs.get_settings", return_value=settings),
            patch(
                "app.tools.docs.fetch_repository_docs",
                new=AsyncMock(return_value=result),
            ) as loader,
            patch("app.tools.docs.website_pages", new=AsyncMock(return_value=[])),
            patch("app.tools.docs.llm_is_configured", return_value=False),
            patch("app.tools.hybrid_docs.retrieve_semantic", side_effect=semantic),
        ):
            clusters, sources, count = await search_official_docs(
                "acme/product",
                None,
                [gap()],
                documentation_source=DocumentationSource(
                    repo="acme/docs", root="guide"
                ),
                repo_docs_max_files=7,
                nvidia_embed_max_passages=17,
            )
        self.assertEqual(loader.call_args.args[1], "acme/docs")
        self.assertEqual(loader.call_args.kwargs["root"], "guide")
        self.assertEqual(observed["settings"].nvidia_embed_max_passages, 17)
        self.assertEqual(loader.call_args.kwargs["settings"].repo_docs_max_files, 7)
        self.assertEqual(count, 1)
        self.assertEqual(
            clusters[0].documentation_coverage.recommended_path, "guide/retries.md"
        )
        self.assertEqual(sources[0].url, page.url)
        self.assertEqual(settings.repo_docs_max_files, 200)

    async def test_model_cannot_claim_documented_when_no_evidence_was_retrieved(self):
        with (
            patch(
                "app.tools.docs._load_relevant_repository_documents",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.tools.docs._assess_coverage_with_model",
                new=AsyncMock(
                    return_value={
                        0: {
                            "status": "documented",
                            "rationale": "Unsupported claim",
                            "recommended_action": "no_change",
                        }
                    }
                ),
            ),
        ):
            clusters, _, _ = await search_official_docs("acme/product", None, [gap()])
        self.assertEqual(clusters[0].documentation_coverage.status, "missing")

    async def test_real_graph_preserves_review_flow_limits_and_inspector_on_reopen(
        self,
    ):
        now = datetime.now(UTC)
        issue = Issue(
            number=1,
            title="How to configure retries?",
            body="Configuration question",
            url="https://github.com/acme/product/issues/1",
            state="open",
            comments_count=3,
            created_at=now,
            updated_at=now,
            source_repo="acme/product",
        )
        document = RepositoryDocument(
            path="docs/retries.md",
            title="Retries",
            content="Configure retries with the retry limit.",
            url="https://github.com/acme/product/blob/main/docs/retries.md",
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("app.run_store.DB_PATH", Path(directory) / "runs.db"),
            patch(
                "app.langgraph_agent.research_repo", new=AsyncMock(return_value=[issue])
            ),
            patch(
                "app.langgraph_agent.research_pull_requests",
                new=AsyncMock(return_value=[]),
            ),
            patch("app.langgraph_agent.llm_is_configured", return_value=False),
            patch("app.tools.cluster.llm_is_configured", return_value=False),
            patch("app.tools.docs.llm_is_configured", return_value=False),
            patch(
                "app.tools.docs._load_relevant_repository_documents",
                new=AsyncMock(return_value=[document]),
            ),
            patch("app.tools.docs.website_pages", new=AsyncMock(return_value=[])),
        ):
            state = await run_agent(
                RunRequest(
                    repo="acme/product",
                    limit=100,
                    repo_docs_max_files=12,
                    nvidia_embed_max_passages=64,
                )
            )
            self.assertEqual(state.status, "completed", state.errors)
            self.assertTrue(state.clusters)
            self.assertTrue(state.clusters[0].draft_markdown)
            self.assertIsNotNone(state.clusters[0].documentation_coverage)
            restored = load_run(state.run_id)
            self.assertEqual(restored.scan_limits["merged_pull_requests"], 100)
            self.assertEqual(restored.scan_limits["repository_documents"], 12)
            self.assertTrue(
                any(e["type"] == "span_completed" for e in restored.operation_events)
            )
            stages = [
                e["stage"]
                for e in restored.operation_events
                if e["type"] == "stage_completed"
            ]
            self.assertLess(stages.index("search_docs"), stages.index("draft"))
            with TestClient(app) as client:
                response = client.get(f"/api/v1/runs/{state.run_id}")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["scan_limits"], restored.scan_limits)
                self.assertIsNotNone(response.json()["usage"])
                self.assertTrue(client.get("/api/v1/usage").json()["runs"])
            RUNS.pop(state.run_id, None)
