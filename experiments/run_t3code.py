"""Run the Jev experiment on live T3Code activity; writes local review artifacts."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def configure() -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
    load_dotenv(ROOT / "backend/.env", override=False)
    if not os.environ.get("MERGE_GATEWAY_API_KEY"):
        auth = Path.home() / ".local/share/opencode/auth.json"
        credential = json.loads(auth.read_text(encoding="utf-8"))["merge-gateway"]
        os.environ["MERGE_GATEWAY_API_KEY"] = credential["key"]
    if not os.environ.get("GITHUB_TOKEN"):
        os.environ["GITHUB_TOKEN"] = subprocess.check_output(
            ["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    os.environ.update(
        MERGE_GATEWAY_PRIMARY_MODEL="openai/gpt-5.6-luna",
        MERGE_GATEWAY_FALLBACK_MODEL="",
        LLM_REASONING_EFFORT="high",
        JEV_SHADOW_ENABLED="true",
        DOCSHOUND_DEMO_SCENARIO="",
        DOCSHOUND_DB_PATH=str(ROOT / "backend/data/jev-t3code.db"),
    )


async def run(limit: int, output: Path) -> None:
    from app import events
    from app.agent import run_agent
    from app.config import get_settings
    from app.state import AgentState, DocumentationSource, RunRequest

    request = RunRequest(
        repo="pingdotgg/t3code",
        limit=limit,
        repo_docs_max_files=500,
        documentation_source=DocumentationSource(
            repo="pingdotgg/t3code",
            root="docs",
            url="https://github.com/pingdotgg/t3code/tree/main/docs",
        ),
        dry_run=True,
    )
    state = AgentState(
        repo=request.repo,
        dry_run=True,
        documentation_source=request.documentation_source,
    )
    directory = output / state.run_id
    directory.mkdir(parents=True, exist_ok=False)
    settings = get_settings()
    manifest = {
        "run_id": state.run_id,
        "started_at": datetime.now(UTC).isoformat(),
        "request": request.model_dump(mode="json"),
        "primary_model": settings.merge_gateway_primary_model,
        "reasoning_effort": settings.llm_reasoning_effort,
        "jev_model": settings.jev_model,
        "nvidia_embeddings": settings.nvidia_embed_enabled,
        "nvidia_rerank": settings.nvidia_rerank_enabled,
        "fork_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(
        f"Run {state.run_id}: Luna/high + Jev shadow; {limit} issues and PRs each",
        flush=True,
    )
    print(f"Artifacts: {directory}", flush=True)

    async def progress():
        with (directory / "events.jsonl").open("w", encoding="utf-8") as handle:
            async for event in events.subscribe(state.run_id):
                handle.write(json.dumps(event, default=str) + "\n")
                handle.flush()
                kind = event.get("type", "event")
                if kind in {
                    "agent_decision",
                    "tool_start",
                    "tool_end",
                    "run_completed",
                }:
                    print(
                        f"{kind}: {event.get('action') or event.get('name') or event.get('status', '')}",
                        flush=True,
                    )

    watcher = asyncio.create_task(progress())
    await asyncio.sleep(0)
    result = await run_agent(request, state=state)
    await watcher
    (directory / "run.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )
    cases = []
    lines = [
        "# T3Code: Luna high with Jev pre-draft review",
        "",
        f"Run: `{state.run_id}`. Status: **{result.status}**.",
        "",
        f"{len(result.issues)} issues, {len(result.pull_requests)} PRs, "
        f"{result.docs_candidates_inspected} documents inspected, "
        f"{len(result.clusters)} findings.",
        "",
        "Jev ran in shadow mode before drafting. Its confidence is not measured "
        "accuracy. Human labels remain empty; disagreements require review.",
        "",
    ]
    for index, cluster in enumerate(result.clusters):
        assessment = cluster.jev_assessment or {}
        coverage = cluster.documentation_coverage
        lines.extend(
            [
                f"## {index + 1}. {cluster.name}",
                "",
                cluster.recurring_question,
                "",
                f"Luna coverage: **{coverage.status if coverage else 'unknown'}**. "
                f"Jev: **{assessment.get('verdict', 'not_checked')}** "
                f"({assessment.get('status', 'not_checked')}).",
                "",
                coverage.rationale if coverage else "No coverage assessment.",
                "",
            ]
        )
        if coverage:
            lines.extend(f"- [{s.title}]({s.url})" for s in coverage.relevant_sources)
            lines.append("")
        if cluster.draft_markdown:
            filename = f"draft-{index + 1:02d}.md"
            (directory / filename).write_text(cluster.draft_markdown, encoding="utf-8")
            lines.extend([f"[Review draft]({filename})", ""])
        cases.append(
            {
                "case_id": f"{state.run_id}:{index}",
                "finding": cluster.name,
                "baseline_coverage": coverage.model_dump(mode="json")
                if coverage
                else None,
                "jev": assessment,
                "human_label": None,
                "human_rationale": None,
            }
        )
    (directory / "cases.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
    if result.usage:
        lines.extend(
            [
                "## Usage",
                "",
                "```json",
                json.dumps(result.usage.summary(), indent=2),
                "```",
            ]
        )
    (directory / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result.status,
                "findings": len(result.clusters),
                "jev": dict(
                    Counter(
                        (c.jev_assessment or {}).get("verdict", "not_checked")
                        for c in result.clusters
                    )
                ),
                "errors": result.errors,
                "report": str(directory / "report.md"),
            }
        ),
        flush=True,
    )
    if result.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/results")
    args = parser.parse_args()
    configure()
    asyncio.run(run(args.limit, args.output))
