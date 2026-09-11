import base64
import unittest
from unittest.mock import patch

import httpx

from app.config import Settings
from app.tools.docs_discovery import DocumentPage
from app.tools.repository_docs import fetch_repository_docs

REVISION = "a" * 40
TREE = "b" * 40
BLOB = "c" * 40
TEXT = "# Remote access\n\nConnect your phone to the running server using an authenticated session."


def entry(path, **kwargs):
    return {
        "path": path,
        "type": "blob",
        "mode": "100644",
        "size": 100,
        "sha": BLOB,
        **kwargs,
    }


def blob(text=TEXT):
    return {"encoding": "base64", "content": base64.b64encode(text.encode()).decode()}


class RepositoryDocumentationTests(unittest.IsolatedAsyncioTestCase):
    async def scan(self, entries, *, override=None, readme=None, **settings):
        requests = []

        def handler(request):
            requests.append(request)
            self.assertEqual(request.url.host, "api.github.com")
            self.assertEqual(request.headers["authorization"], "Bearer test-only-token")
            if override:
                response = override(request)
                if response is not None:
                    return response
            path = request.url.path
            if path == "/repos/acme/project":
                return httpx.Response(200, json={"default_branch": "release/docs"})
            if "/commits/" in path:
                return httpx.Response(
                    200, json={"sha": REVISION, "commit": {"tree": {"sha": TREE}}}
                )
            if "/git/trees/" in path:
                return httpx.Response(200, json={"tree": entries, "truncated": False})
            if "/git/blobs/" in path:
                return httpx.Response(200, json=blob())
            raise AssertionError(path)

        config = Settings(_env_file=None, github_token="test-only-token", **settings)
        with (
            patch("app.tools.repository_docs.get_settings", return_value=config),
            patch("app.tools.docs_discovery.get_settings", return_value=config),
        ):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                result = await fetch_repository_docs(client, "acme/project", readme)
        return result, requests

    async def test_nested_docs_formats_readmes_and_linked_guides_have_pinned_citations(
        self,
    ):
        paths = [
            "docs/user/remote.md",
            "packages/cli/docs/setup.mdx",
            "doc/api.rst",
            "documentation/config.adoc",
            "guides/help.txt",
            "packages/sdk/README.md",
            "CONTRIBUTING.md",
            "howto/Phone Setup.md",
        ]
        ignored = [
            "README.md",
            "src/main.py",
            "node_modules/pkg/docs/a.md",
            "vendor/docs/a.md",
            ".repos/another-project/docs/a.md",
            ".agents/skills/README.md",
            "docs/photo.png",
            "scratch/notes.md",
            "../docs/outside.md",
        ]
        readme = DocumentPage(
            title="README",
            url="https://github.com/acme/project#readme",
            text="[Phone](./howto/Phone%20Setup.md#connect)",
        )
        result, requests = await self.scan(
            [entry(p) for p in paths + ignored]
            + [entry("docs/link.md", mode="120000")],
            readme=readme,
        )
        self.assertEqual(len(result.pages), len(paths))
        self.assertEqual(result.details()["status"], "complete")
        self.assertTrue(all(p.source_type == "repo_docs" for p in result.pages))
        self.assertTrue(all(f"/blob/{REVISION}/" in p.url for p in result.pages))
        self.assertTrue(any("Phone%20Setup.md" in p.url for p in result.pages))
        self.assertTrue(any("release%2Fdocs" in str(r.url) for r in requests))
        self.assertEqual(result.pages[0].text, TEXT)

    async def test_caps_report_omissions_and_prioritize_readme_linked_files(self):
        result, requests = await self.scan(
            [
                entry("docs/a.md"),
                entry("docs/b.md"),
                entry("docs/z.md"),
                entry("docs/huge.md", size=200000),
            ],
            readme=DocumentPage(
                title="README",
                url="https://github.com/acme/project#readme",
                text="[Start here](docs/z.md)",
            ),
            repo_docs_max_files=1,
        )
        self.assertEqual(result.candidate_count, 4)
        self.assertEqual(result.omitted_files, 3)
        self.assertTrue(result.pages[0].url.endswith("/docs/z.md"))
        self.assertEqual(sum("/git/blobs/" in r.url.path for r in requests), 1)
        self.assertEqual(result.details()["status"], "partial")

    async def test_truncated_tree_recovers_docs_with_nonrecursive_traversal(self):
        subtree = "d" * 40

        def override(request):
            if "/git/trees/" not in request.url.path:
                return None
            if request.url.params.get("recursive"):
                return httpx.Response(200, json={"tree": [], "truncated": True})
            if request.url.path.endswith(TREE):
                return httpx.Response(
                    200, json={"tree": [entry("docs", type="tree", sha=subtree)]}
                )
            return httpx.Response(200, json={"tree": [entry("remote.md")]})

        result, _ = await self.scan([], override=override)
        self.assertEqual(len(result.pages), 1)
        self.assertTrue(result.pages[0].url.endswith("/docs/remote.md"))
        self.assertFalse(result.warnings)

    async def test_truncated_tree_budget_is_reported(self):
        def override(request):
            if "/git/trees/" in request.url.path:
                return httpx.Response(
                    200,
                    json={
                        "tree": [entry("docs", type="tree", sha=TREE)],
                        "truncated": bool(request.url.params),
                    },
                )
            return None

        with patch("app.tools.repository_docs.MAX_TREE_REQUESTS", 2):
            result, requests = await self.scan([], override=override)
        self.assertIn("Repository tree traversal limit reached", result.warnings)
        self.assertEqual(sum("/git/trees/" in r.url.path for r in requests), 3)

    async def test_permission_errors_do_not_leak_credentials(self):
        result, _ = await self.scan(
            [], override=lambda r: httpx.Response(403, text="test-only-token")
        )
        self.assertEqual(result.pages, [])
        self.assertIn("GitHub HTTP 403", str(result.warnings))
        self.assertNotIn("test-only-token", str(result.details()))

    async def test_bad_file_does_not_discard_other_docs(self):
        other_blob = "e" * 40

        def override(request):
            if request.url.path.endswith(other_blob):
                return httpx.Response(200, json=blob("binary\x00content"))
            return None

        result, _ = await self.scan(
            [entry("docs/good.md"), entry("docs/bad.md", sha=other_blob)],
            override=override,
        )
        self.assertEqual(len(result.pages), 1)
        self.assertEqual(result.failed_files, 1)
        self.assertEqual(result.details()["status"], "partial")

    async def test_timeout_returns_explicit_partial_status(self):
        def override(request):
            raise httpx.ReadTimeout("test-only-token", request=request)

        result, _ = await self.scan([], override=override)
        self.assertEqual(result.details()["status"], "partial")
        self.assertNotIn("test-only-token", str(result.details()))
