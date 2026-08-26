from collections.abc import Iterable
from typing import Any

from fastapi.templating import Jinja2Templates

_TOOL_LABELS = {
    "research_repo": "research_repo",
    "cluster_issues": "cluster_issues",
    "store_results": "store_results",
    "search_official_docs": "search_official_docs",
}
_STAGE_INDEX = {
    "research": 1,
    "analyze": 2,
    "search_docs": 3,
    "store": 4,
}
_ACTION_LABELS = {
    "research": "Research repository",
    "analyze": "Analyze evidence",
    "search_docs": "Inspect official docs",
    "store": "Finalize run",
}


def _render(templates: Jinja2Templates, name: str, ctx: dict[str, Any]) -> str:
    template = templates.get_template(name)
    return template.render(**ctx).strip()


def _timeline(templates: Jinja2Templates, **ctx: Any) -> str:
    return _render(templates, "_partials/timeline_event.html", ctx)


def _inspector_status(templates: Jinja2Templates, **ctx: Any) -> str:
    return _render(
        templates,
        "_partials/inspector_run_status.html",
        {"oob": True, **ctx},
    )


def _stage_status(templates: Jinja2Templates, **ctx: Any) -> str:
    stage = ctx["stage"]
    return _render(
        templates,
        "_partials/inspector_stage_head.html",
        {
            "stage_index": _STAGE_INDEX[stage],
            "oob": True,
            **ctx,
        },
    )


def _span(templates: Jinja2Templates, event: dict[str, Any], oob: bool) -> str:
    return _render(
        templates,
        "_partials/inspector_span.html",
        {
            "oob": oob,
            "progress_current": None,
            "progress_total": None,
            "progress_detail": None,
            "duration_ms": None,
            "output_summary": None,
            "output_details": {},
            "error": None,
            **event,
        },
    )


def _oob_gaps_count(count: int) -> str:
    return f'<span class="panel-sub" id="gaps-count" hx-swap-oob="outerHTML">{count} found</span>'


def _hide_empty() -> str:
    return '<div class="gaps-empty" id="gaps-empty" hx-swap-oob="outerHTML" hidden></div>'


def render_events(
    event: dict[str, Any],
    templates: Jinja2Templates,
    run_id: str,
) -> Iterable[dict[str, str]]:
    etype = event.get("type")

    if etype == "run_started":
        yield {
            "event": "inspector_oob",
            "data": _inspector_status(
                templates,
                status="running",
                title=f"Starting analysis of {event['repo']}",
                detail="Preparing the agent router and repository context.",
                progress=0,
            ),
        }
        return

    if etype == "agent_thinking":
        yield {
            "event": "inspector_oob",
            "data": _inspector_status(
                templates,
                status="running",
                title=event.get("label") or "Choosing the next action",
                detail=event.get("detail") or "",
                progress=event.get("progress", 0),
            ),
        }
        return

    if etype == "agent_decision":
        reason = event.get("reason") or ""
        action = event.get("action") or "?"
        progress = max(0, _STAGE_INDEX.get(action, 1) - 1)
        yield {
            "event": "inspector_oob",
            "data": _inspector_status(
                templates,
                status="running",
                title=f"Next: {_ACTION_LABELS.get(action, action)}",
                detail=reason,
                progress=progress,
            ),
        }
        return

    if etype == "stage_started":
        stage = event["stage"]
        stage_html = _stage_status(
            templates,
            stage=stage,
            label=event["label"],
            status="running",
            detail=event.get("detail") or "",
            duration_ms=None,
            started_at=event.get("started_at"),
        )
        run_html = _inspector_status(
            templates,
            status="running",
            title=event["label"],
            detail=event.get("detail") or "",
            progress=_STAGE_INDEX[stage] - 1,
        )
        yield {
            "event": "inspector_oob",
            "data": f"{stage_html}{run_html}",
        }
        return

    if etype == "stage_completed":
        stage = event["stage"]
        stage_html = _stage_status(
            templates,
            stage=stage,
            label=event["label"],
            status=event.get("status") or "success",
            detail=event.get("detail") or "",
            duration_ms=event.get("duration_ms"),
            started_at=None,
        )
        run_html = _inspector_status(
            templates,
            status="running",
            title=f"{event['label']} complete",
            detail=event.get("detail") or "",
            progress=_STAGE_INDEX[stage],
        )
        yield {
            "event": "inspector_oob",
            "data": f"{stage_html}{run_html}",
        }
        return

    if etype == "span_started":
        stage = event.get("stage", "analyze")
        yield {
            "event": f"span_{stage}",
            "data": _span(templates, event, oob=False),
        }
        return

    if etype in {"span_progress", "span_completed"}:
        yield {
            "event": "inspector_oob",
            "data": _span(templates, event, oob=True),
        }
        return

    if etype == "tool_start":
        name = event.get("name", "")
        sponsor = event.get("sponsor")
        yield {
            "event": "timeline",
            "data": _timeline(
                templates,
                kind="tool-start",
                icon="▸",
                label=_TOOL_LABELS.get(name, name),
                detail=f"tool: {sponsor}" if sponsor else None,
                meta=None,
            ),
        }
        return

    if etype == "tool_end":
        name = event.get("name", "")
        duration_ms = event.get("duration_ms")
        status = event.get("status")
        if status == "error":
            yield {
                "event": "timeline",
                "data": _timeline(
                    templates,
                    kind="error",
                    icon="✕",
                    label=f"{name} failed",
                    detail=event.get("error") or "",
                    meta=f"{duration_ms} ms" if duration_ms is not None else None,
                ),
            }
        else:
            yield {
                "event": "timeline",
                "data": _timeline(
                    templates,
                    kind="tool-end",
                    icon="✓",
                    label=f"{name} ok",
                    detail=None,
                    meta=f"{duration_ms} ms" if duration_ms is not None else None,
                ),
            }
        return

    if etype == "issues_fetched":
        count = event.get("count", 0)
        yield {
            "event": "timeline",
            "data": _timeline(
                templates,
                kind="success",
                icon="◉",
                label=f"{count} issues fetched",
                detail=None,
                meta=None,
            ),
        }
        return

    if etype == "pull_requests_fetched":
        count = event.get("count", 0)
        yield {
            "event": "timeline",
            "data": _timeline(
                templates,
                kind="success",
                icon="✓",
                label=f"{count} merged pull requests fetched",
                detail=None,
                meta=None,
            ),
        }
        return

    if etype == "gap_found":
        cluster = event["cluster"]
        index = event["index"]
        ctx = {
            "cluster": cluster,
            "index": index,
            "run_id": run_id,
        }
        yield {
            "event": "gap_card",
            "data": _render(templates, "_partials/gap_card.html", ctx),
        }
        yield {"event": "oob", "data": _hide_empty()}
        yield {"event": "oob", "data": _oob_gaps_count(index + 1)}
        return

    if etype == "docs_sources_found":
        count = event.get("count", 0)
        sources = event.get("sources") or []
        detail = ", ".join(source.get("title", "source") for source in sources[:2])
        yield {
            "event": "timeline",
            "data": _timeline(
                templates,
                kind="success",
                icon="◈",
                label=f"{count} official docs sources checked",
                detail=detail or None,
                meta=None,
            ),
        }
        return

    if etype == "gap_approved":
        yield {
            "event": "timeline",
            "data": _timeline(
                templates,
                kind="success",
                icon="✓",
                label="Document approved",
                detail=event.get("title", ""),
                meta=None,
            ),
        }
        return

    if etype == "run_completed":
        status = event.get("status", "completed")
        title = (
            "Run failed"
            if status == "failed"
            else "Run completed with errors"
            if status == "completed_with_errors"
            else "Run completed"
        )
        detail = (
            "; ".join(event.get("errors") or [])
            if event.get("errors")
            else (
                f"{event.get('issues_scraped', 0)} issues · "
                f"{event.get('pull_requests_scraped', 0)} pull requests · "
                f"{event.get('clusters_found', 0)} gaps"
            )
        )
        yield {
            "event": "inspector_oob",
            "data": _inspector_status(
                templates,
                status=status,
                title=title,
                detail=detail,
                progress=4 if status != "failed" else 0,
            ),
        }
        return
