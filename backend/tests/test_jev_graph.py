import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.langgraph_agent import graph
from app.state import GapCluster, Issue
from app.tools.github import research_pull_requests, research_repo


class JevGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_graph_runs_real_jev_nodes_between_analysis_search_and_drafting(self):
        order = []
        issue = Issue(
            number=9352,
            title="Context meter",
            body="Where is the meter?",
            url="https://github.com/pingdotgg/t3code/issues/9352",
            state="open",
            source_repo="pingdotgg/t3code",
            created_at="2026-09-18T00:00:00Z",
            updated_at="2026-09-18T00:00:00Z",
        )
        cluster = GapCluster(
            name="Context meter",
            summary="Explain the setting",
            recurring_question="Where is it?",
            issue_numbers=[9352],
            issue_refs=["pingdotgg/t3code#9352"],
            severity="medium",
            confidence=0.8,
        )

        async def triage(c, issues, prs, **kwargs):
            order.append("triage")
            self.assertEqual(c.implementation_evidence[0]["content"], "setting exists")
            return {
                "status": "succeeded",
                "answers": {"readiness": {"choice": "confirmed"}},
            }

        async def search(repo, url, clusters, **kwargs):
            order.append("search")
            self.assertIsNotNone(clusters[0].jev_triage)
            clusters[0].documentation_evidence = [
                {
                    "path": "docs/a.md",
                    "url": "https://example.com",
                    "content": "context",
                }
            ]
            return clusters, [], 1

        async def review(c, **kwargs):
            order.append("review")
            self.assertEqual(len(c.documentation_evidence), 1)
            return {
                "status": "succeeded",
                "answers": {},
                "recommendation": "review_draft",
            }

        async def draft(clusters, *args):
            order.append("draft")
            self.assertEqual(
                clusters[0].jev_assessment["recommendation"], "review_draft"
            )
            return clusters

        with (
            patch(
                "app.langgraph_agent.get_settings",
                return_value=SimpleNamespace(jev_shadow_enabled=True),
            ),
            patch("app.langgraph_agent.llm_is_configured", return_value=False),
            patch(
                "app.langgraph_agent.research_repo", new=AsyncMock(return_value=[issue])
            ),
            patch(
                "app.langgraph_agent.research_pull_requests",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.langgraph_agent.cluster_issues",
                new=AsyncMock(return_value=[cluster]),
            ),
            patch("app.langgraph_agent.triage_finding", side_effect=triage),
            patch("app.langgraph_agent.search_official_docs", side_effect=search),
            patch("app.langgraph_agent.review_evidence", side_effect=review),
            patch("app.langgraph_agent.draft_review_documents", side_effect=draft),
        ):
            result = await graph.ainvoke(
                {
                    "run_id": "test-jev-graph",
                    "repo": "pingdotgg/t3code",
                    "implementation_evidence": [
                        {
                            "source_refs": ["pingdotgg/t3code#9352"],
                            "content": "setting exists",
                        }
                    ],
                }
            )
        self.assertEqual(order, ["triage", "search", "review", "draft"])
        self.assertTrue(result["stored"])
        self.assertFalse(result.get("errors"))

    async def test_empty_pinned_lists_do_not_fetch_recent_activity(self):
        client = AsyncMock()
        self.assertEqual(
            await research_repo("pingdotgg/t3code", 50, numbers=[], client=client), []
        )
        self.assertEqual(
            await research_pull_requests(
                "pingdotgg/t3code", 50, numbers=[], client=client
            ),
            [],
        )
        client.get.assert_not_called()
