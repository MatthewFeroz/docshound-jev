"""Collect disjoint recent-activity batches and run the real DocsHound agent."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from run_t3code import ROOT, configure, run

REPOSITORIES = {
    "opencode": {
        "repo": "anomalyco/opencode",
        "root": "packages/web/src/content/docs",
        "branch": "dev",
    },
    "pi": {
        "repo": "earendil-works/pi",
        "root": "packages/coding-agent",
        "branch": "main",
    },
}


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


async def collect(name: str, output: Path, limit: int, batch_size: int) -> None:
    from app.tools.github import research_pull_requests, research_repo

    target = REPOSITORIES[name]
    directory = output / name
    directory.mkdir(parents=True, exist_ok=True)
    selection_path = directory / "selection.json"
    if selection_path.exists():
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        if selection["limit"] != limit or selection["batch_size"] != batch_size:
            raise ValueError(
                "Existing selection has different limits; use a new output directory"
            )
    else:
        issues, prs = await asyncio.gather(
            research_repo(target["repo"], limit),
            research_pull_requests(target["repo"], limit),
        )
        selection = {
            "repo": target["repo"],
            "selected_at": datetime.now(UTC).isoformat(),
            "limit": limit,
            "batch_size": batch_size,
            "method": "Recent activity in GitHub API order, all issue states and merged PRs; disjoint contiguous batches; not random or human-labeled.",
            "issue_numbers": [i.number for i in issues],
            "pull_request_numbers": [p.number for p in prs],
            "issues": [i.model_dump(mode="json") for i in issues],
            "pull_requests": [p.model_dump(mode="json") for p in prs],
        }
        save(selection_path, selection)
    issue_numbers = selection["issue_numbers"]
    pr_numbers = selection["pull_request_numbers"]
    print(
        f"Selected {target['repo']}: {len(issue_numbers)} issues, {len(pr_numbers)} merged PRs",
        flush=True,
    )
    if not issue_numbers and not pr_numbers:
        raise RuntimeError("No activity available")
    for offset in range(0, max(len(issue_numbers), len(pr_numbers)), batch_size):
        batch = offset // batch_size + 1
        result_path = directory / f"batch-{batch:02d}-result.json"
        if result_path.exists():
            print(f"Preserving completed batch {batch}", flush=True)
            continue
        request = {
            "repo": target["repo"],
            "limit": batch_size,
            "issue_numbers": issue_numbers[offset : offset + batch_size],
            "pull_request_numbers": pr_numbers[offset : offset + batch_size],
            "repo_docs_max_files": 500,
            "include_documentation_activity": False,
            "documentation_source": {
                "repo": target["repo"],
                "root": target["root"],
                "url": f"https://github.com/{target['repo']}/tree/{target['branch']}/{target['root']}",
            },
            "jev_gate_enabled": True,
            "dry_run": True,
        }
        save(directory / f"batch-{batch:02d}-request.json", request)
        result = await run(
            batch_size,
            directory / "runs",
            hold_unverified=True,
            request_override=request,
        )
        save(result_path, {"batch": batch, "run_id": result.name, "path": str(result)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", choices=REPOSITORIES)
    parser.add_argument(
        "--limit", type=int, choices=range(1, 101), default=100, metavar="1..100"
    )
    parser.add_argument(
        "--batch-size", type=int, choices=range(1, 101), default=20, metavar="1..100"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "experiments/results/cross-repository"
    )
    args = parser.parse_args()
    configure()
    asyncio.run(collect(args.repo, args.output, args.limit, args.batch_size))
