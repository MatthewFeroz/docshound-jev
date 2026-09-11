"""Read bounded, revision-pinned documentation from a repository's default branch."""

import asyncio
import base64
import posixpath
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from urllib.parse import quote, unquote, urlsplit

import httpx

from app.config import Settings, get_settings
from app.state import GapCluster
from app.tools.docs_discovery import DocumentPage, _github_headers

MAX_TREE_REQUESTS = 40
DOC_EXTENSIONS = {".md", ".mdx", ".markdown", ".rst", ".txt", ".adoc"}
DOC_DIRECTORIES = {"doc", "docs", "documentation", "guide", "guides", "tutorials"}
EXCLUDED_DIRECTORIES = {
    ".git",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "__pycache__",
    ".venv",
}
DOC_NAMES = {
    "readme",
    "contributing",
    "installation",
    "getting-started",
    "usage",
    "configuration",
}


@dataclass
class RepositoryDocsResult:
    pages: list[DocumentPage] = field(default_factory=list)
    revision: str | None = None
    candidate_count: int = 0
    omitted_files: int = 0
    failed_files: int = 0
    warnings: list[str] = field(default_factory=list)

    def details(self) -> dict:
        return {
            "status": "partial" if self.warnings else "complete",
            "revision": self.revision,
            "candidate_count": self.candidate_count,
            "page_count": len(self.pages),
            "omitted_files": self.omitted_files,
            "failed_files": self.failed_files,
            "warnings": self.warnings,
            "sources": [page.url for page in self.pages],
        }


def _allowed_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return (
        bool(parts)
        and not path.startswith("/")
        and not any(
            part in {"..", "."}
            or part.lower() in EXCLUDED_DIRECTORIES
            or (part.startswith(".") and part != ".github")
            for part in parts
        )
    )


def _readme_links(readme: DocumentPage | None) -> set[str]:
    if not readme:
        return set()
    links = set()
    for href in re.findall(r"\[[^\]]*\]\(<?([^\s)>]+)>?(?:\s+[^)]*)?\)", readme.text):
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        path = posixpath.normpath(unquote(parsed.path).lstrip("/"))
        if _allowed_path(path):
            links.add(path)
    return links


def _is_doc(path: str, linked: set[str]) -> bool:
    file = PurePosixPath(path.lower())
    if not _allowed_path(path) or file.suffix not in DOC_EXTENSIONS:
        return False
    # The top-level README is already fetched separately.
    if len(file.parts) == 1 and file.stem == "readme":
        return False
    return (
        path in linked
        or any(part in DOC_DIRECTORIES for part in file.parts[:-1])
        or file.stem in DOC_NAMES
    )


async def fetch_repository_docs(
    client: httpx.AsyncClient,
    repo: str,
    readme: DocumentPage | None = None,
    clusters: list[GapCluster] | None = None,
    *,
    settings: Settings | None = None,
    root: str | None = None,
) -> RepositoryDocsResult:
    settings = settings or get_settings()
    result = RepositoryDocsResult()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        result.warnings.append("Invalid repository name")
        return result
    api = f"https://api.github.com/repos/{repo}"
    headers = _github_headers()

    async def get_json(path: str, **kwargs) -> dict:
        response = await client.get(
            api + path, headers=headers, follow_redirects=False, timeout=12, **kwargs
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Invalid GitHub response")
        return data

    async def collect() -> None:
        metadata = await get_json("")
        branch = metadata.get("default_branch")
        if not isinstance(branch, str) or not branch:
            raise ValueError("Default branch unavailable")
        commit = await get_json(f"/commits/{quote(branch, safe='')}")
        revision = commit["sha"]
        tree_sha = commit["commit"]["tree"]["sha"]
        if not all(
            isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40,64}", sha)
            for sha in (revision, tree_sha)
        ):
            raise ValueError("Invalid revision")
        result.revision = revision
        tree = await get_json(f"/git/trees/{tree_sha}", params={"recursive": "1"})
        entries = tree["tree"]
        if tree.get("truncated"):
            # GitHub recommends non-recursive subtree traversal for truncated trees.
            queue = deque([("", tree_sha)])
            entries_by_path = {entry["path"]: entry for entry in entries}
            requests = 0
            while queue and requests < MAX_TREE_REQUESTS:
                prefix, sha = queue.popleft()
                subtree = await get_json(f"/git/trees/{sha}")
                requests += 1
                if subtree.get("truncated"):
                    result.warnings.append("A GitHub subtree listing was truncated")
                for entry in subtree["tree"]:
                    path = posixpath.join(prefix, entry["path"])
                    if not _allowed_path(path):
                        continue
                    entries_by_path[path] = {**entry, "path": path}
                    if entry["type"] == "tree":
                        queue.append((path, entry["sha"]))
                queue = deque(
                    sorted(
                        queue,
                        key=lambda item: (
                            not any(
                                p.lower() in DOC_DIRECTORIES
                                for p in PurePosixPath(item[0]).parts
                            ),
                            item[0],
                        ),
                    )
                )
            if queue:
                result.warnings.append("Repository tree traversal limit reached")
            entries = list(entries_by_path.values())

        linked = _readme_links(readme)
        candidates = [
            entry
            for entry in entries
            if entry.get("type") == "blob"
            and entry.get("mode") in {"100644", "100755"}
            and (
                _is_doc(entry["path"], linked)
                if not root
                else (
                    _allowed_path(entry["path"])
                    and entry["path"].startswith(root.rstrip("/") + "/")
                    and PurePosixPath(entry["path"]).suffix.lower() in DOC_EXTENSIONS
                )
            )
        ]
        from app.tools.docs import _prefer_canonical_paths

        preferred = set(
            _prefer_canonical_paths([entry["path"] for entry in candidates])
        )
        candidates = [entry for entry in candidates if entry["path"] in preferred]
        result.candidate_count = len(candidates)
        eligible = [
            entry
            for entry in candidates
            if type(entry.get("size")) is int
            and 0 < entry["size"] <= settings.repo_docs_max_file_bytes
        ]
        terms = set(
            re.findall(
                r"[a-z0-9_]{3,}",
                " ".join(
                    f"{gap.name} {gap.summary} {gap.recurring_question}"
                    for gap in (clusters or [])
                ).lower(),
            )
        )
        eligible.sort(
            key=lambda entry: (
                entry["path"] not in linked,
                not any(
                    p in DOC_DIRECTORIES for p in entry["path"].lower().split("/")[:-1]
                ),
                -len(terms & set(re.findall(r"[a-z0-9_]{3,}", entry["path"].lower()))),
                entry["path"].lower(),
            )
        )
        selected = eligible[: settings.repo_docs_max_files]
        result.omitted_files = len(candidates) - len(selected)
        if result.omitted_files:
            result.warnings.append(
                "Some documentation files exceeded the file count or size limits"
            )
        semaphore = asyncio.Semaphore(6)

        async def fetch(entry: dict) -> None:
            async with semaphore:
                try:
                    sha = entry["sha"]
                    if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
                        raise ValueError("Invalid blob revision")
                    payload = await get_json(f"/git/blobs/{sha}")
                    if payload.get("encoding") != "base64":
                        raise ValueError("Unsupported blob encoding")
                    content = payload["content"]
                    if len(content) > settings.repo_docs_max_file_bytes * 2:
                        raise ValueError("Blob too large")
                    raw = base64.b64decode("".join(content.split()), validate=True)
                    if len(raw) > settings.repo_docs_max_file_bytes or b"\x00" in raw:
                        raise ValueError("Unsupported documentation content")
                    text = raw.decode("utf-8-sig")
                    if not text.strip():
                        raise ValueError("Empty document")
                    path = entry["path"]
                    heading = re.search(r"^#{1,2}\s+(.+)$", text, re.MULTILINE)
                    title = f"{heading.group(1).strip()} ({path})" if heading else path
                    result.pages.append(
                        DocumentPage(
                            title=title[:200],
                            url=(
                                f"https://github.com/{repo}/blob/{revision}/{quote(path, safe='/')}"
                            ),
                            text=text,
                            source_type="repo_docs",
                        )
                    )
                except httpx.HTTPError, ValueError, KeyError, TypeError:
                    result.failed_files += 1

        await asyncio.gather(*(fetch(entry) for entry in selected))
        # Stable ordering makes ranking ties and cache behavior reproducible.
        result.pages.sort(key=lambda page: page.url)
        if result.failed_files:
            result.warnings.append(
                "Some repository documentation files could not be read"
            )

    try:
        async with asyncio.timeout(settings.repo_docs_timeout_seconds):
            await collect()
    except TimeoutError:
        result.warnings.append("Repository documentation scan timed out")
    except httpx.HTTPStatusError as exc:
        result.warnings.append(
            f"Repository documentation discovery: GitHub HTTP {exc.response.status_code}"
        )
    except httpx.RequestError, ValueError, KeyError, TypeError:
        result.warnings.append("Repository documentation discovery failed")
    return result
