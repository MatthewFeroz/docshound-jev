from collections.abc import Callable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from time import perf_counter, time
from typing import Any, Literal
from uuid import uuid4

from langsmith import trace as langsmith_trace

from app import events

RunType = Literal["tool", "retriever"]


@dataclass(frozen=True)
class OperationSpec:
    stage: str
    label: str
    description: str
    run_type: RunType = "tool"


STAGE_LABELS = {
    "research": "Research repository",
    "analyze": "Analyze evidence",
    "search_docs": "Inspect official docs",
    "store": "Finalize run",
    "draft": "Draft documentation",
}

OPERATION_SPECS = {
    "retrieve_semantic_docs": OperationSpec(
        stage="search_docs",
        label="Find documentation by meaning",
        description="Combine Nemotron embeddings with keyword search and report fallback use.",
        run_type="retriever",
    ),
    "research_repo": OperationSpec(
        stage="research",
        label="Fetch GitHub issues",
        description="Read recent issue titles, discussions, labels, and activity.",
    ),
    "research_pull_requests": OperationSpec(
        stage="research",
        label="Fetch merged pull requests",
        description="Read recently shipped changes that may need documentation.",
    ),
    "cluster_issues": OperationSpec(
        stage="analyze",
        label="Cluster recurring questions",
        description="Group repository evidence into distinct documentation gaps.",
    ),
    "draft_findings": OperationSpec(
        stage="analyze",
        label="Draft review findings",
        description="Turn each evidence cluster into a reviewable Markdown draft.",
    ),
    "search_official_docs": OperationSpec(
        stage="search_docs",
        label="Search official documentation",
        description="Discover, retrieve, and assess first-party documentation.",
    ),
    "discover_docs_root": OperationSpec(
        stage="search_docs",
        label="Locate documentation site",
        description="Resolve the first-party docs root from configuration and repository metadata.",
    ),
    "discover_document_urls": OperationSpec(
        stage="search_docs",
        label="Map documentation pages",
        description="Read robots.txt, sitemaps, and navigation to find in-scope pages.",
    ),
    "fetch_document_pages": OperationSpec(
        stage="search_docs",
        label="Retrieve documentation pages",
        description="Fetch and extract readable content from the bounded docs corpus.",
        run_type="retriever",
    ),
    "fetch_repository_readme": OperationSpec(
        stage="search_docs",
        label="Retrieve repository README",
        description="Load the repository README as first-party fallback evidence.",
        run_type="retriever",
    ),
    "fetch_repository_docs": OperationSpec(
        stage="search_docs",
        label="Read repository documentation",
        description=(
            "Find documentation files on the default branch and retain revision-specific citations."
        ),
        run_type="retriever",
    ),
    "rank_docs_for_gaps": OperationSpec(
        stage="search_docs",
        label="Rank evidence for each gap",
        description="Chunk and score retrieved documentation against each gap.",
    ),
    "assess_doc_coverage": OperationSpec(
        stage="search_docs",
        label="Assess documentation coverage",
        description="Classify each gap as covered, partial, or missing using cited excerpts.",
    ),
    "rerank_docs_for_gap": OperationSpec(
        stage="search_docs",
        label="Rerank documentation evidence",
        description="Use NVIDIA to prioritize candidate passages; report any search fallback.",
    ),
}

_CURRENT_RUN_ID: ContextVar[str | None] = ContextVar(
    "docshound_run_id",
    default=None,
)
_CURRENT_REPO: ContextVar[str | None] = ContextVar(
    "docshound_repo",
    default=None,
)
_CURRENT_STAGE: ContextVar[str | None] = ContextVar(
    "docshound_stage",
    default=None,
)
_CURRENT_SPAN_ID: ContextVar[str | None] = ContextVar(
    "docshound_span_id",
    default=None,
)
_CURRENT_SPAN_DEPTH: ContextVar[int] = ContextVar(
    "docshound_span_depth",
    default=-1,
)
_CURRENT_SPAN_EVENT: ContextVar[dict[str, Any] | None] = ContextVar(
    "docshound_span_event",
    default=None,
)
_STAGE_STARTS: dict[tuple[str, str], float] = {}


@contextmanager
def traced_run(run_id: str, repo: str):
    """Attach local observability context to the LangGraph invocation."""
    run_token = _CURRENT_RUN_ID.set(run_id)
    repo_token = _CURRENT_REPO.set(repo)
    try:
        yield None
    finally:
        _CURRENT_REPO.reset(repo_token)
        _CURRENT_RUN_ID.reset(run_token)


def stage_started(
    run_id: str,
    stage: str,
    detail: str,
) -> None:
    started_at = time()
    _STAGE_STARTS[(run_id, stage)] = perf_counter()
    events.publish(
        run_id,
        {
            "type": "stage_started",
            "stage": stage,
            "label": STAGE_LABELS[stage],
            "status": "running",
            "detail": detail,
            "started_at": started_at,
        },
    )


def stage_completed(
    run_id: str,
    stage: str,
    summary: str,
    status: Literal["success", "error"] = "success",
) -> None:
    started = _STAGE_STARTS.pop((run_id, stage), None)
    duration_ms = (
        round((perf_counter() - started) * 1000, 1) if started is not None else None
    )
    events.publish(
        run_id,
        {
            "type": "stage_completed",
            "stage": stage,
            "label": STAGE_LABELS[stage],
            "status": status,
            "detail": summary,
            "duration_ms": duration_ms,
        },
    )


def publish_span_progress(
    current: int,
    total: int,
    detail: str,
) -> None:
    """Publish progress for the operation active in this async context."""
    run_id = _CURRENT_RUN_ID.get()
    base_event = _CURRENT_SPAN_EVENT.get()
    if not run_id or not base_event:
        return
    events.publish(
        run_id,
        {
            **base_event,
            "type": "span_progress",
            "status": "running",
            "progress_current": current,
            "progress_total": total,
            "progress_detail": detail,
        },
    )


async def run_traced(
    name: str,
    run_id: str,
    repo: str,
    fn: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Run a top-level graph operation with local and LangSmith observability."""
    run_token = _CURRENT_RUN_ID.set(run_id)
    repo_token = _CURRENT_REPO.set(repo)
    try:
        return await observe_operation(name, fn, *args, **kwargs)
    finally:
        _CURRENT_REPO.reset(repo_token)
        _CURRENT_RUN_ID.reset(run_token)


async def observe_operation(
    name: str,
    fn: Callable[..., Any],
    *args: Any,
    input_summary: str | None = None,
    input_details: Mapping[str, Any] | None = None,
    output_summary: str | Callable[[Any], str] | None = None,
    output_details: (
        Mapping[str, Any] | Callable[[Any], Mapping[str, Any]] | None
    ) = None,
    trace_outputs: Callable[[Any], dict[str, Any]] | None = None,
    **kwargs: Any,
) -> Any:
    """Trace one inspectable operation and publish its live UI lifecycle."""
    spec = OPERATION_SPECS.get(
        name,
        OperationSpec(
            stage=_CURRENT_STAGE.get() or "analyze",
            label=name.replace("_", " ").title(),
            description="Run an agent operation.",
        ),
    )
    run_id = _CURRENT_RUN_ID.get()
    repo = _CURRENT_REPO.get()
    parent_span_id = _CURRENT_SPAN_ID.get()
    depth = _CURRENT_SPAN_DEPTH.get() + 1
    span_id = str(uuid4())
    started_at = time()
    safe_inputs = dict(input_details or _default_input_details(name, args))
    summary_in = input_summary or _default_input_summary(name, safe_inputs)

    base_event = {
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "stage": spec.stage,
        "category": spec.run_type,
        "name": name,
        "label": spec.label,
        "description": spec.description,
        "input_summary": summary_in,
        "input_details": safe_inputs,
        "started_at": started_at,
        "depth": depth,
    }
    trace_inputs = {
        "summary": summary_in,
        **safe_inputs,
    }
    metadata = {
        "docshound_run_id": run_id,
        "repo": repo,
        "stage": spec.stage,
        "operation": name,
    }

    async with langsmith_trace(
        name,
        run_type=spec.run_type,
        inputs=trace_inputs,
        metadata=metadata,
        tags=["docshound-operation", spec.stage],
        run_id=span_id,
    ) as trace_run:
        trace_id = str(trace_run.trace_id)
        start_event = {
            **base_event,
            "type": "span_started",
            "status": "running",
            "trace_id": trace_id,
        }
        if run_id:
            events.publish(run_id, start_event)

        run_token = _CURRENT_RUN_ID.set(run_id)
        repo_token = _CURRENT_REPO.set(repo)
        stage_token = _CURRENT_STAGE.set(spec.stage)
        span_token = _CURRENT_SPAN_ID.set(span_id)
        depth_token = _CURRENT_SPAN_DEPTH.set(depth)
        event_token = _CURRENT_SPAN_EVENT.set(start_event)
        started = perf_counter()
        try:
            result = fn(*args, **kwargs)
            if hasattr(result, "__await__"):
                result = await result
        except Exception as exc:
            if run_id:
                events.publish(
                    run_id,
                    {
                        **base_event,
                        "type": "span_completed",
                        "status": "error",
                        "trace_id": trace_id,
                        "duration_ms": round(
                            (perf_counter() - started) * 1000,
                            1,
                        ),
                        "output_summary": "Operation failed",
                        "output_details": {},
                        "error": str(exc),
                    },
                )
            raise
        else:
            summary_out = _resolve_output_summary(
                name,
                result,
                output_summary,
            )
            details_out = _resolve_output_details(
                name,
                result,
                output_details,
            )
            traced_outputs = (
                trace_outputs(result)
                if trace_outputs
                else {"result": summary_out, **details_out}
            )
            trace_run.end(outputs=traced_outputs)
            if run_id:
                events.publish(
                    run_id,
                    {
                        **base_event,
                        "type": "span_completed",
                        "status": "success",
                        "trace_id": trace_id,
                        "duration_ms": round(
                            (perf_counter() - started) * 1000,
                            1,
                        ),
                        "output_summary": summary_out,
                        "output_details": details_out,
                        "error": None,
                    },
                )
            return result
        finally:
            _CURRENT_SPAN_EVENT.reset(event_token)
            _CURRENT_SPAN_DEPTH.reset(depth_token)
            _CURRENT_SPAN_ID.reset(span_token)
            _CURRENT_STAGE.reset(stage_token)
            _CURRENT_REPO.reset(repo_token)
            _CURRENT_RUN_ID.reset(run_token)


def _default_input_details(
    name: str,
    args: tuple[Any, ...],
) -> dict[str, Any]:
    if name in {"research_repo", "research_pull_requests"}:
        return {
            "repository": args[0] if args else None,
            "limit": args[1] if len(args) > 1 else None,
        }
    if name == "cluster_issues":
        return {
            "issues": len(args[0]) if args else 0,
            "pull_requests": len(args[1]) if len(args) > 1 else 0,
        }
    if name == "draft_findings":
        return {
            "clusters": len(args[0]) if args else 0,
            "issues": len(args[1]) if len(args) > 1 else 0,
            "pull_requests": len(args[2]) if len(args) > 2 else 0,
        }
    if name == "search_official_docs":
        return {
            "repository": args[0] if args else None,
            "docs_url": args[1] if len(args) > 1 else None,
            "gaps": len(args[2]) if len(args) > 2 else 0,
        }
    return {}


def _default_input_summary(
    name: str,
    details: Mapping[str, Any],
) -> str:
    if name in {"research_repo", "research_pull_requests"}:
        return f"{details.get('repository')} · limit {details.get('limit')}"
    if name == "cluster_issues":
        return f"{details.get('issues', 0)} issues · {details.get('pull_requests', 0)} pull requests"
    if name == "draft_findings":
        return f"{details.get('clusters', 0)} evidence clusters"
    if name == "search_official_docs":
        return f"{details.get('repository')} · {details.get('gaps', 0)} gaps"
    return "Prepared operation inputs"


def _resolve_output_summary(
    name: str,
    result: Any,
    summary: str | Callable[[Any], str] | None,
) -> str:
    if callable(summary):
        return summary(result)
    if summary:
        return summary
    count = len(result) if hasattr(result, "__len__") else None
    if name == "research_repo":
        return f"{count or 0} issues fetched"
    if name == "research_pull_requests":
        return f"{count or 0} merged pull requests fetched"
    if name == "cluster_issues":
        return f"{count or 0} documentation gaps identified"
    if name == "draft_findings":
        return f"{count or 0} findings drafted"
    if name == "search_official_docs":
        return f"{count or 0} cited documentation sources returned"
    return "Operation completed"


def _resolve_output_details(
    name: str,
    result: Any,
    details: Mapping[str, Any] | Callable[[Any], Mapping[str, Any]] | None,
) -> dict[str, Any]:
    if callable(details):
        return dict(details(result))
    if details is not None:
        return dict(details)
    if hasattr(result, "__len__"):
        return {"result_count": len(result)}
    return {}


def observed_stage(stage):
    def decorate(fn):
        @wraps(fn)
        async def wrapped(state):
            stage_started(state["run_id"], stage, STAGE_LABELS[stage])
            before = len(state.get("errors", []))
            status = "success"
            try:
                result = await fn(state)
                if len(result.get("errors", [])) > before:
                    status = "error"
                return result
            except Exception:
                status = "error"
                raise
            finally:
                stage_completed(
                    state["run_id"],
                    stage,
                    STAGE_LABELS[stage]
                    + " "
                    + ("complete" if status == "success" else "failed"),
                    status,
                )

        return wrapped

    return decorate
