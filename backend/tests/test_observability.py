import unittest
from unittest.mock import patch
from uuid import UUID

from app import events
from app.observability import publish_span_progress, run_traced


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
            "app.observability.langsmith_trace",
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


if __name__ == "__main__":
    unittest.main()
