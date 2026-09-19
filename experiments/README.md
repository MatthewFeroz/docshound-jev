# Jev pre-draft experiment

This isolated DocsHound fork checks whether Jev can identify unsupported findings
before Luna drafts documentation. The original DocsHound checkout is untouched.

```powershell
uv run --project backend --locked python experiments/run_t3code.py
```

The runner uses GPT-5.6 Luna with high reasoning through Merge, checks up to 50
open issues and 50 merged PRs, and inspects up to 500 documentation files under
T3Code's `docs/` directory. These limits do not mean all historical GitHub activity
or all repository code is sent to the models. Repository documentation URLs are
pinned by the existing retrieval implementation to the commit fetched at run time.

NVIDIA embeddings and reranking retain their existing retrieval role when enabled.
Jev sees the same ranked excerpts used by the coverage model, the proposed finding,
and Luna's coverage hypothesis. It returns `supported_gap`, `already_documented`,
or `insufficient_evidence`. The hypothesis is explicitly not ground truth.

Jev runs in shadow mode: it records a verdict before drafting but does not change
coverage, review status, or whether a draft is generated. A timeout, invalid reply,
or missing evidence remains unavailable, never a successful negative judgment.
The feature is opt-in with `JEV_SHADOW_ENABLED=true` outside the experiment runner.

Credentials are read from environment/ignored `.env` files; the runner can reuse
OpenCode's saved Merge key and GitHub CLI authentication. It writes a separate
`backend/data/jev-t3code.db`. No issues, branches, or PRs are published to T3Code.

Each `experiments/results/<run-id>/` directory contains the run, event trace,
model settings, exact Jev requests, costs, blank human labels, drafts, and a report.
Results are ignored by Git. Jev's request contains no draft, human review, or later
outcome fields. Confidence is a model output, not empirical accuracy.

Review disagreements against the actual source documents, then label cases
independently. Separate `insufficient_evidence` from false findings. Measure false
gap detection, useful drafts incorrectly flagged, abstentions, latency and cost.
Do not claim savings from this shadow run: it intentionally drafts as usual.
Use additional repositories and group repeated topics when constructing holdouts.
