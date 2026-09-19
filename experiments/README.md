# DocsHound Jev experiments

The current runnable demo is documented in [demo/jev](../demo/jev/README.md).
It includes a saved real run, a video script, a retrospective, and two proposed
T3Code documentation patches.

From the repository root:

```powershell
uv run --project backend --locked python experiments/run_t3code.py --demo --hold-unverified
uv run --project backend --locked python experiments/serve_demo.py
```

Open http://127.0.0.1:8017/jev. The live button invokes the same LangGraph agent
through the API. For a broad scan instead of the selected cases, omit `--demo`.

The graph uses GPT-5.6 Luna with high reasoning through Merge. Jev's first node
classifies finding type, implementation readiness, and audience from original
GitHub activity and any supplied implementation snippets. The second node
classifies each retrieved passage and the documentation need. Code derives an
advisory next step. NVIDIA retains its optional embedding and reranking roles.

Selected issue and PR numbers are inputs, not fixed model outputs. The manifest
at `t3code-demo.json` records how cases were chosen and pins source-code excerpts.
Documentation URLs preserve the revision fetched during each run. All Jev
classifications are live; the recorded-run importer is an explicitly separate
replay path.

The optional `--hold-unverified` gate holds findings whose recommendation is
`verify_implementation` before drafting. Without it, recommendations are advisory.
Retrieval recommendations do not automatically trigger another search yet.
Luna's original coverage assessment remains available for comparison.
Missing credentials, timeouts, and invalid model responses yield an unavailable
classification and manual review, not a successful negative verdict.

Credentials are read from environment/ignored `.env` files, with OpenCode's saved
Merge credential and GitHub CLI authentication as launcher fallbacks. The demo
uses its own `backend/data/jev-t3code.db`. No upstream GitHub writes occur.

CLI artifacts are stored in ignored `experiments/results/<run-id>/` directories:
request manifest, event trace, final state, exact Jev request envelopes, model
usage, draft Markdown, blank human labels, and a report. The portable recording
omits original issue bodies and request envelopes while retaining classifications
and displayed evidence. Model confidence is not empirical accuracy.

The first experiment's broad support judgment remains in `assess_finding` for
backward comparison; the current graph uses the more specific v2 classifiers.
See the retrospective before making quality or cost-saving claims.

## Larger repository samples

`run_repositories.py` scans OpenCode (`anomalyco/opencode`) and Pi from pi.dev
(`earendil-works/pi`). It records up to 100 issues and 100 merged PRs for each,
then runs disjoint batches of 20 issues and 20 PRs through the same agent with
the Jev verification gate enabled. It saves the input selection and skips
completed batches on restart.

```powershell
uv run --project backend --locked python experiments/run_repositories.py opencode
uv run --project backend --locked python experiments/run_repositories.py pi
uv run --project backend --locked python experiments/summarize_repositories.py
```

The [results and review dataset](../demo/jev/cross-repository/README.md) count
source items, findings, passages and model requests separately. These runs use
recent activity without handpicked implementation snippets. Human labels are
blank; the dataset does not establish classification accuracy. Completed runs
are available in the Jev Lab selector on the same local instance.

For another repository, write a `RunRequest` JSON and pass it to
`run_t3code.py --request path/to/request.json --hold-unverified`. Omit
`--hold-unverified` for an advisory run. All runner invocations stay in dry-run
mode and publish no upstream changes.
