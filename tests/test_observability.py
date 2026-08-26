import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from fastapi.templating import Jinja2Templates

from app import events
from app.render import render_events
from app.tracing import publish_span_progress, run_traced

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parents[1] / "app" / "web" / "templates"))


class _FakeTraceRun:
    trace_id = UUID("11111111-1111-1111-1111-111111111111")

    def __init__(self) -> None:
        self.outputs = None

    def end(self, outputs=None) -> None:
        self.outputs = outputs


class _FakeTrace:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.run = _FakeTraceRun()

    async def __aenter__(self) -> _FakeTraceRun:
        return self.run

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class ObservabilityEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_operation_emits_linked_start_progress_and_completion(self) -> None:
        run_id = "observability-test-run"

        async def fetch_issues(repo: str, limit: int) -> list[int]:
            publish_span_progress(1, 2, "1 of 2 · first page")
            return [1, 2]

        with patch(
            "app.tracing.langsmith_trace",
            side_effect=_FakeTrace,
        ):
            result = await run_traced(
                "research_repo",
                run_id,
                "acme/product",
                fetch_issues,
                "acme/product",
                2,
            )

        events.close(run_id)
        recorded = [event async for event in events.subscribe(run_id)]

        self.assertEqual(result, [1, 2])
        self.assertEqual(
            [event["type"] for event in recorded],
            ["span_started", "span_progress", "span_completed"],
        )
        self.assertEqual(
            {event["span_id"] for event in recorded},
            {recorded[0]["span_id"]},
        )
        self.assertEqual(recorded[0]["stage"], "research")
        self.assertEqual(recorded[0]["category"], "tool")
        self.assertEqual(recorded[1]["progress_current"], 1)
        self.assertEqual(recorded[1]["progress_total"], 2)
        self.assertEqual(recorded[2]["status"], "success")
        self.assertEqual(recorded[2]["output_summary"], "2 issues fetched")
        self.assertEqual(
            recorded[2]["trace_id"],
            "11111111-1111-1111-1111-111111111111",
        )


class ObservabilityRenderingTests(unittest.TestCase):
    def test_span_start_appends_to_its_stage(self) -> None:
        rendered = list(
            render_events(
                {
                    "type": "span_started",
                    "span_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "parent_span_id": None,
                    "trace_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "stage": "research",
                    "category": "tool",
                    "name": "research_repo",
                    "label": "Fetch GitHub issues",
                    "description": "Read recent issues.",
                    "input_summary": "acme/product · limit 50",
                    "input_details": {
                        "repository": "acme/product",
                        "limit": 50,
                    },
                    "started_at": 100,
                    "depth": 0,
                    "status": "running",
                },
                TEMPLATES,
                "run-123",
            )
        )

        self.assertEqual(rendered[0]["event"], "span_research")
        self.assertIn(
            'id="span-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"',
            rendered[0]["data"],
        )
        self.assertIn("Fetch GitHub issues", rendered[0]["data"])
        self.assertIn("type-tool", rendered[0]["data"])

    def test_span_completion_replaces_the_existing_row(self) -> None:
        rendered = list(
            render_events(
                {
                    "type": "span_completed",
                    "span_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "parent_span_id": None,
                    "trace_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "stage": "research",
                    "category": "tool",
                    "name": "research_repo",
                    "label": "Fetch GitHub issues",
                    "description": "Read recent issues.",
                    "input_summary": "acme/product · limit 50",
                    "input_details": {
                        "repository": "acme/product",
                        "limit": 50,
                    },
                    "output_summary": "50 issues fetched",
                    "output_details": {"result_count": 50},
                    "started_at": 100,
                    "duration_ms": 2140,
                    "depth": 0,
                    "status": "success",
                    "error": None,
                },
                TEMPLATES,
                "run-123",
            )
        )

        self.assertEqual(rendered[0]["event"], "inspector_oob")
        self.assertIn('hx-swap-oob="outerHTML"', rendered[0]["data"])
        self.assertIn("50 issues fetched", rendered[0]["data"])
        self.assertIn("2.1s", rendered[0]["data"])

    def test_stage_start_updates_stage_and_run_header(self) -> None:
        rendered = list(
            render_events(
                {
                    "type": "stage_started",
                    "stage": "search_docs",
                    "label": "Inspect official docs",
                    "detail": "Discovering first-party documentation.",
                    "started_at": 100,
                },
                TEMPLATES,
                "run-123",
            )
        )

        self.assertEqual(rendered[0]["event"], "inspector_oob")
        self.assertIn('id="stage-status-search_docs"', rendered[0]["data"])
        self.assertIn('id="inspector-run-status"', rendered[0]["data"])
        self.assertIn("Inspect official docs", rendered[0]["data"])


if __name__ == "__main__":
    unittest.main()
