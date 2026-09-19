"""Live source selection for the recording; never supplies model verdicts."""

import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.runtime_credentials import get_github_api_token
from app.state import DocumentationSource, RunRequest


def manifest() -> dict:
    path = Path(__file__).resolve().parents[2] / "experiments/t3code-demo.json"
    return json.loads(path.read_text(encoding="utf-8"))


async def demo_request(*, hold_unverified: bool = False) -> RunRequest:
    selection = manifest()
    repo, revision = selection["repo"], selection["revision"]
    token = get_github_api_token() or get_settings().github_token
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    evidence = []
    async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
        for source in selection["source_files"]:
            path = source["path"]
            response = await client.get(
                f"https://api.github.com/repos/{repo}/contents/{quote(path, safe='/')}",
                params={"ref": revision},
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("encoding") != "base64":
                raise ValueError("Source evidence is not an inline file")
            content = base64.b64decode(payload["content"]).decode("utf-8")
            lines = content.splitlines()
            start, end = source["start_line"], source["end_line"]
            if not 1 <= start <= end <= len(lines):
                raise ValueError("Source evidence line range is invalid")
            excerpt = "\n".join(lines[start - 1 : end])
            evidence.append(
                {
                    **source,
                    "revision": revision,
                    "content": excerpt,
                    "sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
                    "url": f"https://github.com/{repo}/blob/{revision}/{path}#L{start}-L{end}",
                }
            )
    return RunRequest(
        jev_gate_enabled=hold_unverified,
        repo=repo,
        issue_numbers=selection["issue_numbers"],
        pull_request_numbers=selection["pull_request_numbers"],
        implementation_evidence=evidence,
        limit=50,
        repo_docs_max_files=500,
        documentation_source=DocumentationSource(
            repo=repo,
            root="docs",
            url=f"https://github.com/{repo}/tree/main/docs",
        ),
        dry_run=True,
    )
