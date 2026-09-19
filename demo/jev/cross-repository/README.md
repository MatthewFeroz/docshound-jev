# OpenCode and Pi: expanded Jev experiment

Real DocsHound runs using Luna high, NVIDIA retrieval and Jev with the verification gate enabled. No upstream issues, PRs or documentation were published.

| Repository | Runs | Unique issues | Unique merged PRs | Findings | Held | Drafted | Jev requests | Jev cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| anomalyco/opencode | 5 | 100 | 100 | 37 | 22 | 14 | 74 | $0.00667666 |
| earendil-works/pi | 5 | 100 | 100 | 34 | 22 | 5 | 68 | $0.00560427 |

Total: **400 distinct source items, 71 findings, 142 Jev requests and 497 answered classification questions**. Jev reported $0.01228093; all Merge calls reported $0.226708, excluding unpriced providers. 0 model calls failed.

## Interpretation

Source items, generated findings, model requests and classification questions are different denominators. Findings within a run can share source references; repeated topics across batches are not independent samples.

Selection uses recent GitHub API activity, all issue states and merged PRs, partitioned into disjoint batches of 20 issues and 20 PRs. These are convenience samples, not random or held-out data. Bodies are fetched again during each run and preserved in local artifacts. No implementation snippets were manually supplied, unlike the selected T3Code demo. Repository documentation is revision-pinned when fetched; website pages are also retrieved and may be unversioned. Documents inspected includes both sources and is not a unique-file count across runs.

A held finding is not a proven bad draft. There are zero independent human labels. No accuracy, precision, recall or savings claim follows from these counts. Provider-reported costs exclude unpriced calls, including NVIDIA. Retrieval advice remains advisory.

Pi activity spans its monorepo, while the configured repository documentation root is `packages/coding-agent` plus discovered website pages. Other packages may require a broader documentation scope. OpenCode uses `packages/web/src/content/docs` plus discovered website pages. Treat these collection boundaries as potential explanations for a gap, not proof that documentation is absent everywhere.

## Inspect the runs

### anomalyco/opencode

Readiness: `{"needs_verification": 22, "confirmed": 15}`. Recommendations: `{"verify_implementation": 22, "review_draft": 7, "retrieve_more": 8}`.

Passage classifications: `{"useful_background": 63, "unrelated": 46, "direct_answer": 2}`. These are Jev predictions, not relevance labels.

Of 22 held findings, 21 had a Luna coverage verdict and recommended action that made them eligible for drafting. The remaining holds overlap Luna's existing nondrafting decisions; do not count them as additional drafts prevented.

Jev status: `{"succeeded": 74}`; 0 failed model calls. Reported Merge cost: $0.126978; 81 unpriced calls.

- [Run 4a50fa89](http://127.0.0.1:8017/jev?run=4a50fa89-b168-4dda-a369-6dfd1b3c6e30): 7 findings, 5 held, 2 drafted; completed; 72 documents inspected.
- [Run 599c2a8c](http://127.0.0.1:8017/jev?run=599c2a8c-9825-4515-bf1c-2dfe54e7ab8d): 7 findings, 4 held, 3 drafted; completed; 72 documents inspected.
- [Run 80949f17](http://127.0.0.1:8017/jev?run=80949f17-a8ad-4572-ba67-04ed84bfcdf5): 7 findings, 3 held, 4 drafted; completed; 72 documents inspected.
- [Run a9f14797](http://127.0.0.1:8017/jev?run=a9f14797-1929-439b-b69e-193e32c40e37): 8 findings, 6 held, 2 drafted; completed; 72 documents inspected.
- [Run b446159d](http://127.0.0.1:8017/jev?run=b446159d-13d2-4adc-95d6-8c30ca75d2e1): 8 findings, 4 held, 3 drafted; completed; 72 documents inspected.

### earendil-works/pi

Readiness: `{"needs_verification": 22, "confirmed": 12}`. Recommendations: `{"verify_implementation": 22, "no_change": 4, "retrieve_more": 5, "review_draft": 3}`.

Passage classifications: `{"useful_background": 86, "unrelated": 8, "direct_answer": 8}`. These are Jev predictions, not relevance labels.

Of 22 held findings, 12 had a Luna coverage verdict and recommended action that made them eligible for drafting. The remaining holds overlap Luna's existing nondrafting decisions; do not count them as additional drafts prevented.

Jev status: `{"succeeded": 68}`; 0 failed model calls. Reported Merge cost: $0.099730; 101 unpriced calls.

- [Run 2bbbcd20](http://127.0.0.1:8017/jev?run=2bbbcd20-85ad-4aaf-bd65-2a6c90d39ff6): 8 findings, 6 held, 0 drafted; completed; 97 documents inspected.
- [Run 3c823f3f](http://127.0.0.1:8017/jev?run=3c823f3f-3af8-4eee-ae43-051fdb4d5808): 5 findings, 2 held, 3 drafted; completed; 97 documents inspected.
- [Run b2afba88](http://127.0.0.1:8017/jev?run=b2afba88-a810-40bd-96df-b67a903efe18): 8 findings, 5 held, 2 drafted; completed; 97 documents inspected.
- [Run b5795582](http://127.0.0.1:8017/jev?run=b5795582-8225-4b45-87f1-daf5fdd46854): 7 findings, 5 held, 0 drafted; completed; 97 documents inspected.
- [Run f02cd4c6](http://127.0.0.1:8017/jev?run=f02cd4c6-cbba-479f-8084-597cc9a98eca): 6 findings, 4 held, 0 drafted; completed; 97 documents inspected.

## Labeling and reproduction

`cases.jsonl` contains one row per finding, source references, Luna coverage, Jev distributions, retrieved excerpts, actual hold/draft outcomes, and blank human labels. `sampling.json` preserves the selected IDs. Full original bodies, drafts, model requests and traces remain in ignored `experiments/results/cross-repository/<project>/runs/<run-id>/` and the local demo database.

For a blinded review, hide model verdicts and review the source evidence first. Label whether the behavior is established, whether documentation needs changing, and each passage's relevance. Record uncertainty and a rationale; do not infer a correct label from an open/closed issue or Jev confidence. Review both held and passed findings. Group related source references and topics before train/test splitting.

```powershell
uv run --project backend --locked python experiments/run_repositories.py opencode
uv run --project backend --locked python experiments/run_repositories.py pi
uv run --project backend --locked python experiments/summarize_repositories.py
```

The batch runner preserves its selection and skips completed batches. Use a new `--output` directory for a fresh collection. Raw input bodies are not included in this portable export.
