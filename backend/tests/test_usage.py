import asyncio
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from langchain_core.messages import AIMessage

from app.config import Settings
from app.run_store import load_run, save_run
from app.state import RUNS, AgentState, RunRequest
from app.tools.nvidia_embed import _embed
from app.usage import (
    PRICING,
    ModelCallUsage,
    RunUsage,
    record_langchain_response,
    track_model_call,
    track_run_usage,
)


def report():
    return {
        "prompt_tokens": 1000,
        "completion_tokens": 200,
        "total_tokens": 1200,
        "prompt_tokens_details": {"cached_tokens": 400},
        "completion_tokens_details": {"reasoning_tokens": 100},
    }


class UsageTests(unittest.IsolatedAsyncioTestCase):
    def test_cached_input_discount_and_reasoning_not_double_counted(self):
        usage = RunUsage()
        with track_run_usage(usage, lambda: None):
            with track_model_call("openai", "gpt-5.6-luna", "clustering") as call:
                call.report(report())
        self.assertEqual(call.total_tokens, 1200)
        self.assertEqual(call.reasoning_tokens, 100)
        self.assertAlmostEqual(call.estimated_cost_usd, 0.000368)
        self.assertEqual(usage.summary()["total_tokens"], 1200)
        self.assertEqual(call.request_status, "succeeded")

    def test_unknown_models_tiers_and_missing_usage_are_not_free(self):
        for provider, model, tier in (
            ("nvidia", "embed", None),
            ("openai", "unknown", None),
            ("openai", "gpt-5.6-luna", "priority"),
        ):
            call = ModelCallUsage(
                provider=provider, model=model, requested_model=model, operation="test"
            )
            call.report(report(), service_tier=tier)
            self.assertIsNone(call.estimated_cost_usd)
        call = ModelCallUsage(
            provider="nvidia",
            model="rerank",
            requested_model="rerank",
            operation="reranking",
        )
        call.report(None)
        self.assertIsNone(call.input_tokens)
        self.assertEqual(call.usage_status, "unavailable")
        self.assertIsNone(RunUsage(calls=[call]).summary()["estimated_cost_usd"])

    def test_embedding_counts_and_malformed_counts(self):
        call = ModelCallUsage(
            provider="nvidia",
            model="embed",
            requested_model="embed",
            operation="embed_passage",
        )
        call.report({"prompt_tokens": 99, "total_tokens": 99})
        self.assertEqual(
            (call.input_tokens, call.output_tokens, call.total_tokens), (99, 0, 99)
        )
        call.report({"prompt_tokens": True, "completion_tokens": -1})
        self.assertIsNone(call.input_tokens)
        self.assertIsNone(call.output_tokens)

    def test_parsing_failure_keeps_usage_and_does_not_store_response_content(self):
        usage = RunUsage()
        with self.assertRaises(ValueError), track_run_usage(usage, lambda: None):
            with track_model_call("openai", "gpt-5.6-luna", "coverage") as call:
                raw = AIMessage(
                    content="secret response",
                    usage_metadata={
                        "input_tokens": 1000,
                        "output_tokens": 200,
                        "total_tokens": 1200,
                        "input_token_details": {"cache_read": 400},
                        "output_token_details": {"reasoning": 100},
                    },
                    response_metadata={"model_name": "gpt-5.6-luna"},
                )
                record_langchain_response(
                    call,
                    {"raw": raw, "parsed": None, "parsing_error": ValueError("secret")},
                )
        self.assertEqual(call.request_status, "failed")
        self.assertAlmostEqual(call.estimated_cost_usd, 0.000368)
        self.assertNotIn("secret", usage.model_dump_json())

    async def test_parallel_calls_share_only_their_own_run_and_count_failures(self):
        async def run(model):
            usage = RunUsage()

            async def request(fail=False):
                try:
                    with track_model_call("openai", model, "routing") as call:
                        await asyncio.sleep(0)
                        if fail:
                            raise RuntimeError("private error body")
                        call.report(report())
                except RuntimeError:
                    pass

            with track_run_usage(usage, lambda: None):
                await asyncio.gather(request(), request(), request(True))
            return usage

        first, second = await asyncio.gather(run("gpt-5.6-luna"), run("different"))
        self.assertEqual(first.summary()["call_count"], 3)
        self.assertEqual(first.summary()["failed_calls"], 1)
        self.assertEqual(first.summary()["calls_without_full_usage"], 1)
        self.assertEqual(first.summary()["total_tokens"], 2400)
        self.assertTrue(all(c.model == "different" for c in second.calls))
        self.assertIsNone(second.summary()["estimated_cost_usd"])
        self.assertNotIn("private", first.model_dump_json())

    def test_usage_persists_on_each_call_and_pricing_snapshot_survives_changes(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("app.run_store.DB_PATH", Path(directory) / "runs.db"),
        ):
            state = AgentState(repo="acme/project", usage=RunUsage())

            def save():
                save_run(state)

            with track_run_usage(state.usage, save):
                with track_model_call("openai", "gpt-5.6-luna", "routing") as call:
                    self.assertEqual(
                        load_run(state.run_id).usage.calls[0].request_status, "pending"
                    )
                    call.report(report())
            with patch.dict(PRICING, {"gpt-5.6-luna": {"input": "99"}}):
                loaded = load_run(state.run_id)
                self.assertEqual(
                    loaded.usage.calls[0].pricing_snapshot["input"], "0.20"
                )
                self.assertAlmostEqual(
                    loaded.usage.summary()["estimated_cost_usd"], 0.000368
                )
            old = AgentState(repo="acme/old")
            save_run(old)
            self.assertIsNone(load_run(old.run_id).usage)

    def test_langchain_success_returns_parsed_object(self):
        call = ModelCallUsage(
            provider="openai",
            model="gpt-5.6-luna",
            requested_model="gpt-5.6-luna",
            operation="routing",
        )
        parsed = SimpleNamespace(action="research")
        raw = AIMessage(
            content="",
            response_metadata={"token_usage": report(), "model_name": "gpt-5.6-luna"},
        )
        result = record_langchain_response(
            call, {"raw": raw, "parsed": parsed, "parsing_error": None}
        )
        self.assertIs(result, parsed)
        self.assertEqual(call.total_tokens, 1200)

    async def test_failed_agent_run_keeps_provider_usage_in_database(self):
        from app.agent import run_agent

        async def failed_graph(*args, **kwargs):
            with track_model_call("openai", "gpt-5.6-luna", "routing") as call:
                call.report(report())
            raise RuntimeError("Graph failed after inference")

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("app.run_store.DB_PATH", Path(directory) / "runs.db"),
            patch("app.agent.graph.ainvoke", side_effect=failed_graph),
            patch("app.agent.traced_run", return_value=nullcontext()),
        ):
            state = await run_agent(RunRequest(repo="acme/project", limit=1))
            loaded = load_run(state.run_id)
            self.assertEqual(loaded.status, "failed")
            self.assertEqual(loaded.usage.summary()["total_tokens"], 1200)
            self.assertAlmostEqual(
                loaded.usage.summary()["estimated_cost_usd"], 0.000368
            )
            RUNS.pop(state.run_id, None)

    async def test_nvidia_embedding_batches_record_provider_reported_tokens(self):
        def handler(request):
            inputs = json.loads(request.content)["input"]
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": i, "embedding": [1.0, 0.0]}
                        for i in range(len(inputs))
                    ],
                    "usage": {
                        "prompt_tokens": len(inputs) * 5,
                        "total_tokens": len(inputs) * 5,
                    },
                },
            )

        usage = RunUsage()
        with track_run_usage(usage, lambda: None):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                await _embed(
                    client,
                    ["Test document"] * 20,
                    "passage",
                    Settings(_env_file=None, nvidia_api_key="test"),
                )
        self.assertEqual(usage.summary()["call_count"], 2)
        self.assertEqual(usage.summary()["input_tokens"], 100)
        self.assertEqual(usage.summary()["total_tokens"], 100)
        self.assertEqual(usage.summary()["calls_with_usage"], 2)
        self.assertIsNone(usage.summary()["estimated_cost_usd"])


if __name__ == "__main__":
    unittest.main()
