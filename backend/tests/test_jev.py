import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from app.config import Settings
from app.jev import assess_finding, recommend, review_evidence, triage_finding
from app.state import DocumentationCoverage, GapCluster, Issue


class JevTests(unittest.IsolatedAsyncioTestCase):
    async def test_triage_uses_original_matching_activity_without_future_fields(self):
        self.cluster.issue_refs = ["pingdotgg/t3code#1"]
        payload = dict(
            number=1,
            title="Original issue",
            body="original source text",
            url="https://github.com/pingdotgg/t3code/issues/1",
            state="open",
            created_at="2026-09-18T00:00:00Z",
            updated_at="2026-09-18T00:00:00Z",
        )
        issues = [
            Issue(**payload, source_repo="pingdotgg/t3code"),
            Issue(**{**payload, "body": "wrong repository"}, source_repo="other/repo"),
        ]
        with patch("app.jev.decide", new=AsyncMock(return_value={})) as call:
            await triage_finding(self.cluster, issues, [], settings=self.settings)
        state = call.await_args.args[0]
        self.assertEqual(len(state["source_activity"]), 1)
        self.assertEqual(state["source_activity"][0]["body"], "original source text")
        self.assertNotIn("FUTURE_DRAFT", json.dumps(state))
        self.assertNotIn("documentation_coverage", state["finding"])

    async def test_evidence_check_is_independent_of_luna_coverage(self):
        self.cluster.documentation_evidence = [
            {**self.evidence[0], "url": "https://example.com/doc"}
        ]
        with patch(
            "app.jev.decide",
            new=AsyncMock(return_value={"status": "unavailable", "answers": {}}),
        ) as call:
            record = await review_evidence(self.cluster, settings=self.settings)
        state, questions = call.await_args.args
        self.assertNotIn("proposed_assessment", state)
        self.assertNotIn("documentation_coverage", json.dumps(state))
        self.assertEqual(set(questions), {"gap_kind", "document_0"})
        self.assertEqual(record["recommendation"], "manual_review")

    def test_no_evidence_routes_to_retrieval_and_unverified_behavior_to_verification(
        self,
    ):
        triage = {
            "status": "succeeded",
            "answers": {"readiness": {"choice": "confirmed"}},
        }
        review = {
            "status": "succeeded",
            "answers": {
                "gap_kind": {"choice": "missing_procedure"},
                "document_0": {"choice": "unrelated"},
            },
        }
        self.assertEqual(recommend(triage, review), "retrieve_more")
        review["answers"]["document_0"]["choice"] = "useful_background"
        self.assertEqual(recommend(triage, review), "review_draft")
        triage["answers"]["readiness"]["choice"] = "needs_verification"
        self.assertEqual(recommend(triage, review), "verify_implementation")

    def setUp(self):
        self.settings = Settings(_env_file=None, merge_gateway_api_key="test")
        self.cluster = GapCluster(
            name="Remote setup",
            summary="Need remote setup instructions",
            recurring_question="How do I connect remotely?",
            issue_numbers=[1],
            severity="medium",
            confidence=0.7,
            draft_markdown="FUTURE_DRAFT",
            review_status="approved",
            documentation_coverage=DocumentationCoverage(
                status="partial",
                rationale="Connection step absent",
                recommended_action="update_page",
            ),
        )
        self.evidence = [{"path": "docs/remote.md", "content": "Connect over SSH."}]

    async def test_success_keeps_drafting_and_excludes_future_labels(self):
        before = self.cluster.model_dump()
        response = httpx.Response(
            200,
            request=httpx.Request("POST", "https://example.com"),
            json={
                "model": "jev-1.13.0",
                "answers": {
                    "support": {
                        "type": "choice",
                        "choice": "already_documented",
                        "confidence": 0.9,
                        "probabilities": {
                            "supported_gap": 0.05,
                            "already_documented": 0.9,
                            "insufficient_evidence": 0.05,
                        },
                    }
                },
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 10,
                    "total_tokens": 110,
                    "cost": 0.0000042,
                },
            },
        )
        client = Mock(post=AsyncMock(return_value=response))
        context = AsyncMock()
        context.__aenter__.return_value = client
        with patch("app.jev.httpx.AsyncClient", return_value=context):
            result = await assess_finding(
                self.cluster,
                self.evidence,
                search_complete=True,
                settings=self.settings,
            )
        self.assertEqual(result["verdict"], "already_documented")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(self.cluster.model_dump(), before)
        state = json.loads(result["request"]["state"])
        self.assertNotIn("FUTURE_DRAFT", result["request"]["state"])
        self.assertNotIn("review_status", state["finding"])
        self.assertIsNone(result["human_label"])
        self.assertEqual(
            client.post.await_args.kwargs["headers"]["Authorization"], "Bearer test"
        )

    async def test_no_evidence_abstains_without_request(self):
        with patch("app.jev.httpx.AsyncClient") as client:
            result = await assess_finding(
                self.cluster, [], search_complete=True, settings=self.settings
            )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "no_evidence")
        client.assert_not_called()

    async def test_timeout_does_not_stop_drafting_or_leak_error(self):
        client = Mock(
            post=AsyncMock(side_effect=httpx.ReadTimeout("secret-error-body"))
        )
        context = AsyncMock()
        context.__aenter__.return_value = client
        with patch("app.jev.httpx.AsyncClient", return_value=context):
            result = await assess_finding(
                self.cluster,
                self.evidence,
                search_complete=True,
                settings=self.settings,
            )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "ReadTimeout")
        self.assertNotIn("secret-error-body", json.dumps(result))
        self.assertTrue(self.cluster.is_documentation_proposal)

    async def test_malformed_answer_is_unavailable(self):
        response = httpx.Response(
            200,
            request=httpx.Request("POST", "https://example.com"),
            json={
                "answers": {
                    "support": {
                        "type": "choice",
                        "choice": "invented",
                        "confidence": 1,
                        "probabilities": {},
                    }
                },
            },
        )
        context = AsyncMock()
        context.__aenter__.return_value = Mock(post=AsyncMock(return_value=response))
        with patch("app.jev.httpx.AsyncClient", return_value=context):
            result = await assess_finding(
                self.cluster,
                self.evidence,
                search_complete=True,
                settings=self.settings,
            )
        self.assertEqual(result["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
