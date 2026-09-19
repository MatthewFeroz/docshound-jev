"""Export measured cross-repository results and an unlabeled review dataset."""

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

from run_t3code import ROOT


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def portable(record: dict | None) -> dict:
    return {k: v for k, v in (record or {}).items() if k != "request"}


def summarize(source: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    summaries = []
    cases = []
    sampling = []
    for selection_path in sorted(source.glob("*/selection.json")):
        selection = read(selection_path)
        sampling.append(
            {k: v for k, v in selection.items() if k not in {"issues", "pull_requests"}}
        )
        runs = []
        for path in sorted((selection_path.parent / "runs").glob("*/run.json")):
            state = read(path)
            manifest = read(path.parent / "manifest.json")
            runs.append((state, manifest))
        if not runs:
            continue
        issue_ids, pr_ids, doc_urls = set(), set(), set()
        recommendations, readiness, gap_kinds, relevance, coverage = (
            Counter() for _ in range(5)
        )
        calls, jev_records, durations = [], [], []
        run_summaries = []
        for state, manifest in runs:
            issue_ids.update(i["number"] for i in state["issues"])
            pr_ids.update(p["number"] for p in state["pull_requests"])
            calls.extend((state.get("usage") or {}).get("calls", []))
            run_cases = []
            for index, cluster in enumerate(state["clusters"]):
                triage = portable(cluster.get("jev_triage"))
                review = portable(cluster.get("jev_assessment"))
                for record in (triage, review):
                    if record:
                        jev_records.append(record)
                        if record.get("duration_ms") is not None:
                            durations.append(record["duration_ms"])
                recommendations[review.get("recommendation", "not_checked")] += 1
                readiness[
                    triage.get("answers", {})
                    .get("readiness", {})
                    .get("choice", "not_checked")
                ] += 1
                gap_kinds[
                    review.get("answers", {})
                    .get("gap_kind", {})
                    .get("choice", "not_checked")
                ] += 1
                baseline = cluster.get("documentation_coverage") or {}
                coverage[baseline.get("status", "not_checked")] += 1
                for doc in review.get("documents", []):
                    relevance[
                        (doc.get("answer") or {}).get("choice", "unavailable")
                    ] += 1
                for doc in cluster.get("documentation_evidence", []):
                    doc_urls.add(doc["url"])
                case = {
                    "case_id": f"{state['run_id']}:{index}",
                    "repo": state["repo"],
                    "run_id": state["run_id"],
                    "finding_index": index,
                    "finding": cluster["name"],
                    "summary": cluster["summary"],
                    "question": cluster["recurring_question"],
                    "issue_refs": cluster["issue_refs"],
                    "pr_refs": cluster["pr_refs"],
                    "baseline_coverage": baseline,
                    "baseline_draftable": baseline.get("status")
                    in {"missing", "partial"}
                    and baseline.get("recommended_action") != "no_change",
                    "triage": triage,
                    "jev": review,
                    "draft_hold": cluster.get("jev_draft_hold"),
                    "draft_generated": bool(cluster.get("draft_markdown")),
                    "documentation_evidence": cluster.get("documentation_evidence", []),
                    "human_labels": {
                        "readiness": None,
                        "documentation_need": None,
                        "passage_relevance": None,
                        "hold_appropriate": None,
                        "rationale": None,
                    },
                }
                cases.append(case)
                run_cases.append(case)
            run_summaries.append(
                {
                    "run_id": state["run_id"],
                    "started_at": manifest["started_at"],
                    "status": state["status"],
                    "issues": len(state["issues"]),
                    "merged_prs": len(state["pull_requests"]),
                    "documents_inspected": state["docs_candidates_inspected"],
                    "documentation_source": manifest["request"]["documentation_source"],
                    "findings": len(run_cases),
                    "held": sum(bool(c["draft_hold"]) for c in run_cases),
                    "drafts": sum(c["draft_generated"] for c in run_cases),
                    "errors": state["errors"],
                    "warnings": state["warnings"],
                    "fork_commit": manifest["fork_commit"],
                }
            )
        repo_cases = [c for c in cases if c["repo"] == selection["repo"]]
        summaries.append(
            {
                "repo": selection["repo"],
                "runs": run_summaries,
                "unique_issues": len(issue_ids),
                "unique_merged_prs": len(pr_ids),
                "findings": len(repo_cases),
                "drafts_held": sum(bool(c["draft_hold"]) for c in repo_cases),
                "drafts_generated": sum(c["draft_generated"] for c in repo_cases),
                "holds_on_luna_draftable": sum(
                    bool(c["draft_hold"]) and c["baseline_draftable"]
                    for c in repo_cases
                ),
                "readiness": dict(readiness),
                "recommendations": dict(recommendations),
                "documentation_need": dict(gap_kinds),
                "passage_relevance": dict(relevance),
                "luna_coverage": dict(coverage),
                "unique_cited_document_urls": len(doc_urls),
                "jev_requests": len(jev_records),
                "jev_statuses": dict(Counter(r.get("status") for r in jev_records)),
                "jev_answered_questions": sum(
                    len(r.get("answers", {})) for r in jev_records
                ),
                "jev_reported_cost_usd": sum(
                    (r.get("usage") or {}).get("cost", 0) for r in jev_records
                ),
                "jev_median_duration_ms": median(durations) if durations else None,
                "merge_reported_cost_usd": sum(
                    c.get("reported_cost_usd") or 0
                    for c in calls
                    if c["provider"] == "merge"
                ),
                "failed_model_calls": sum(
                    c["request_status"] == "failed" for c in calls
                ),
                "unpriced_model_calls": sum(
                    c.get("reported_cost_usd") is None
                    and c.get("estimated_cost_usd") is None
                    for c in calls
                ),
                "human_labeled_findings": 0,
            }
        )
    total_fields = (
        "unique_issues",
        "unique_merged_prs",
        "findings",
        "drafts_held",
        "drafts_generated",
        "holds_on_luna_draftable",
        "jev_requests",
        "jev_answered_questions",
        "jev_reported_cost_usd",
        "merge_reported_cost_usd",
        "failed_model_calls",
        "unpriced_model_calls",
        "human_labeled_findings",
    )
    data = {
        "generated_at": datetime.now(UTC).isoformat(),
        "totals": {
            field: sum(repo[field] for repo in summaries) for field in total_fields
        },
        "repositories": summaries,
    }
    (output / "summary.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (output / "sampling.json").write_text(
        json.dumps(sampling, indent=2), encoding="utf-8"
    )
    (output / "cases.jsonl").write_text(
        "".join(json.dumps(case) + "\n" for case in cases), encoding="utf-8"
    )
    lines = [
        "# OpenCode and Pi: expanded Jev experiment",
        "",
        "Real DocsHound runs using Luna high, NVIDIA retrieval and Jev with the verification gate enabled. No upstream issues, PRs or documentation were published.",
        "",
        "| Repository | Runs | Unique issues | Unique merged PRs | Findings | Held | Drafted | Jev requests | Jev cost |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for repo in summaries:
        lines.append(
            f"| {repo['repo']} | {len(repo['runs'])} | {repo['unique_issues']} | {repo['unique_merged_prs']} | {repo['findings']} | {repo['drafts_held']} | {repo['drafts_generated']} | {repo['jev_requests']} | ${repo['jev_reported_cost_usd']:.8f} |"
        )
    totals = data["totals"]
    lines.extend(
        [
            "",
            f"Total: **{totals['unique_issues'] + totals['unique_merged_prs']} distinct source items, {totals['findings']} findings, {totals['jev_requests']} Jev requests and {totals['jev_answered_questions']} answered classification questions**. Jev reported ${totals['jev_reported_cost_usd']:.8f}; all Merge calls reported ${totals['merge_reported_cost_usd']:.6f}, excluding unpriced providers. {totals['failed_model_calls']} model calls failed.",
        ]
    )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Source items, generated findings, model requests and classification questions are different denominators. Findings within a run can share source references; repeated topics across batches are not independent samples.",
            "",
            "Selection uses recent GitHub API activity, all issue states and merged PRs, partitioned into disjoint batches of 20 issues and 20 PRs. These are convenience samples, not random or held-out data. Bodies are fetched again during each run and preserved in local artifacts. No implementation snippets were manually supplied, unlike the selected T3Code demo. Repository documentation is revision-pinned when fetched; website pages are also retrieved and may be unversioned. Documents inspected includes both sources and is not a unique-file count across runs.",
            "",
            "A held finding is not a proven bad draft. There are zero independent human labels. No accuracy, precision, recall or savings claim follows from these counts. Provider-reported costs exclude unpriced calls, including NVIDIA. Retrieval advice remains advisory.",
            "",
            "Pi activity spans its monorepo, while the configured repository documentation root is `packages/coding-agent` plus discovered website pages. Other packages may require a broader documentation scope. OpenCode uses `packages/web/src/content/docs` plus discovered website pages. Treat these collection boundaries as potential explanations for a gap, not proof that documentation is absent everywhere.",
            "",
            "## Inspect the runs",
            "",
        ]
    )
    for repo in summaries:
        lines.extend(
            [
                f"### {repo['repo']}",
                "",
                f"Readiness: `{json.dumps(repo['readiness'])}`. Recommendations: `{json.dumps(repo['recommendations'])}`.",
                "",
                f"Passage classifications: `{json.dumps(repo['passage_relevance'])}`. These are Jev predictions, not relevance labels.",
                "",
                f"Of {repo['drafts_held']} held findings, {repo['holds_on_luna_draftable']} had a Luna coverage verdict and recommended action that made them eligible for drafting. The remaining holds overlap Luna's existing nondrafting decisions; do not count them as additional drafts prevented.",
                "",
                f"Jev status: `{json.dumps(repo['jev_statuses'])}`; {repo['failed_model_calls']} failed model calls. Reported Merge cost: ${repo['merge_reported_cost_usd']:.6f}; {repo['unpriced_model_calls']} unpriced calls.",
                "",
            ]
        )
        for run in repo["runs"]:
            lines.append(
                f"- [Run {run['run_id'][:8]}](http://127.0.0.1:8017/jev?run={run['run_id']}): {run['findings']} findings, {run['held']} held, {run['drafts']} drafted; {run['status']}; {run['documents_inspected']} documents inspected."
            )
        lines.append("")
    lines.extend(
        [
            "## Labeling and reproduction",
            "",
            "`cases.jsonl` contains one row per finding, source references, Luna coverage, Jev distributions, retrieved excerpts, actual hold/draft outcomes, and blank human labels. `sampling.json` preserves the selected IDs. Full original bodies, drafts, model requests and traces remain in ignored `experiments/results/cross-repository/<project>/runs/<run-id>/` and the local demo database.",
            "",
            "For a blinded review, hide model verdicts and review the source evidence first. Label whether the behavior is established, whether documentation needs changing, and each passage's relevance. Record uncertainty and a rationale; do not infer a correct label from an open/closed issue or Jev confidence. Review both held and passed findings. Group related source references and topics before train/test splitting.",
            "",
            "```powershell",
            "uv run --project backend --locked python experiments/run_repositories.py opencode",
            "uv run --project backend --locked python experiments/run_repositories.py pi",
            "uv run --project backend --locked python experiments/summarize_repositories.py",
            "```",
            "",
            "The batch runner preserves its selection and skips completed batches. Use a new `--output` directory for a fresh collection. Raw input bodies are not included in this portable export.",
            "",
        ]
    )
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "findings": len(cases),
                "repositories": len(summaries),
                "output": str(output),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=ROOT / "experiments/results/cross-repository"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "demo/jev/cross-repository"
    )
    args = parser.parse_args()
    summarize(args.source, args.output)
