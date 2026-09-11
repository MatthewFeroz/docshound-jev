"""Provider-reported usage, isolated per run and persisted independently of model output."""

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

# Standard API rates, USD per million tokens; snapshots are saved on each priced call.
PRICING = {
    "gpt-5.6-luna": {
        "input": "0.20",
        "cached_input": "0.02",
        "output": "1.20",
        "verified_on": "2026-09-10",
        "source": "https://developers.openai.com/api/docs/models/gpt-5.6-luna",
    },
}


def _mapping(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump()
    return {}


def _count(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


class ModelCallUsage(BaseModel):
    call_id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider: str
    operation: str
    requested_model: str
    model: str
    request_status: Literal["pending", "succeeded", "failed"] = "pending"
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    usage_status: Literal["unavailable", "partial", "reported"] = "unavailable"
    estimated_cost_usd: float | None = None
    pricing_snapshot: dict[str, str] | None = None
    service_tier: str | None = None

    def report(
        self,
        usage: object,
        *,
        model: str | None = None,
        service_tier: str | None = None,
    ) -> None:
        data = _mapping(usage)
        self.usage_status = "unavailable"
        if isinstance(model, str) and model:
            self.model = model
        self.service_tier = service_tier if isinstance(service_tier, str) else None
        self.input_tokens = _count(data.get("input_tokens", data.get("prompt_tokens")))
        self.output_tokens = _count(
            data.get("output_tokens", data.get("completion_tokens"))
        )
        if self.operation.startswith("embed_") and self.input_tokens is not None:
            self.output_tokens = 0  # Embeddings do not generate completion tokens.
        input_details = _mapping(
            data.get("input_token_details", data.get("prompt_tokens_details"))
        )
        output_details = _mapping(
            data.get("output_token_details", data.get("completion_tokens_details"))
        )
        self.cached_input_tokens = _count(
            input_details.get("cache_read", input_details.get("cached_tokens"))
        )
        self.reasoning_tokens = _count(
            output_details.get("reasoning", output_details.get("reasoning_tokens"))
        )
        self.total_tokens = _count(data.get("total_tokens"))
        if self.input_tokens is not None and self.output_tokens is not None:
            inconsistent = self.total_tokens is not None and (
                self.total_tokens != self.input_tokens + self.output_tokens
            )
            self.total_tokens = self.input_tokens + self.output_tokens
            self.usage_status = "partial" if inconsistent else "reported"
        elif any(
            value is not None
            for value in (self.input_tokens, self.output_tokens, self.total_tokens)
        ):
            self.usage_status = "partial"
        if self.cached_input_tokens is not None and (
            self.input_tokens is None or self.cached_input_tokens > self.input_tokens
        ):
            self.cached_input_tokens = None
            self.usage_status = "partial"
        if self.reasoning_tokens is not None and (
            self.output_tokens is None or self.reasoning_tokens > self.output_tokens
        ):
            self.reasoning_tokens = None
            self.usage_status = "partial"
        self._price()

    def _price(self) -> None:
        self.estimated_cost_usd = None
        self.pricing_snapshot = None
        if (
            self.provider != "openai"
            or self.usage_status != "reported"
            or self.service_tier not in {None, "default", "auto", "standard"}
        ):
            return
        model = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", self.model)
        rates = PRICING.get(model)
        if not rates or self.input_tokens > 272_000:
            return  # Unknown models, nonstandard tiers and long-context rates are not guessed.
        self.pricing_snapshot = dict(rates)
        cached = self.cached_input_tokens or 0
        amount = (
            Decimal(self.input_tokens - cached) * Decimal(rates["input"])
            + Decimal(cached) * Decimal(rates["cached_input"])
            + Decimal(self.output_tokens) * Decimal(rates["output"])
        ) / Decimal(1_000_000)
        # Reasoning tokens are already included in output_tokens; never charge twice.
        self.estimated_cost_usd = float(amount)


class RunUsage(BaseModel):
    calls: list[ModelCallUsage] = Field(default_factory=list)

    def summary(self) -> dict:
        groups: dict[tuple[str, str, str], list[ModelCallUsage]] = {}
        for call in self.calls:
            groups.setdefault((call.provider, call.model, call.operation), []).append(
                call
            )
        return {
            **_totals(self.calls),
            "groups": [
                {
                    "provider": provider,
                    "model": model,
                    "operation": operation,
                    **_totals(calls),
                }
                for (provider, model, operation), calls in groups.items()
            ],
        }


def _totals(calls: list[ModelCallUsage]) -> dict:
    priced = [call for call in calls if call.estimated_cost_usd is not None]
    return {
        "call_count": len(calls),
        "pending_calls": sum(c.request_status == "pending" for c in calls),
        "failed_calls": sum(c.request_status == "failed" for c in calls),
        "calls_with_usage": sum(c.usage_status == "reported" for c in calls),
        "calls_without_full_usage": sum(c.usage_status != "reported" for c in calls),
        "unpriced_calls": len(calls) - len(priced),
        "input_tokens": sum(c.input_tokens or 0 for c in calls),
        "output_tokens": sum(c.output_tokens or 0 for c in calls),
        "cached_input_tokens": sum(c.cached_input_tokens or 0 for c in calls),
        "reasoning_tokens": sum(c.reasoning_tokens or 0 for c in calls),
        "total_tokens": sum(c.total_tokens or 0 for c in calls),
        "estimated_cost_usd": (
            float(sum(Decimal(str(c.estimated_cost_usd)) for c in priced))
            if priced
            else None
        ),
    }


_CURRENT_USAGE: ContextVar[tuple[RunUsage, Callable[[], None]] | None] = ContextVar(
    "docshound_usage",
    default=None,
)


@contextmanager
def track_run_usage(usage: RunUsage, on_change: Callable[[], None]) -> Iterator[None]:
    token = _CURRENT_USAGE.set((usage, on_change))
    try:
        yield
    finally:
        _CURRENT_USAGE.reset(token)


@contextmanager
def track_model_call(
    provider: str, model: str, operation: str
) -> Iterator[ModelCallUsage]:
    call = ModelCallUsage(
        provider=provider, model=model, requested_model=model, operation=operation
    )
    context = _CURRENT_USAGE.get()
    if context:
        usage, on_change = context
        usage.calls.append(call)
        on_change()  # Save pending requests too, so interrupted runs do not appear free.
    try:
        yield call
    except BaseException:
        call.request_status = "failed"
        raise
    else:
        call.request_status = "succeeded"
    finally:
        if context:
            on_change()


def record_langchain_response(call: ModelCallUsage, result: dict) -> object:
    raw = result.get("raw")
    metadata = _mapping(getattr(raw, "response_metadata", None))
    usage = getattr(raw, "usage_metadata", None) or metadata.get("token_usage")
    call.report(
        usage,
        model=metadata.get("model_name"),
        service_tier=metadata.get("service_tier"),
    )
    # Capture usage before raising a parsing error; failed parsing can still consume tokens.
    if result.get("parsing_error") or result.get("parsed") is None:
        raise ValueError("Model response could not be parsed")
    return result["parsed"]
