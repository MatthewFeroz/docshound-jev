# DocsHound × Jev: T3Code demo

The agent runs real GitHub research, Luna analysis, Jev classification, NVIDIA
retrieval, Jev evidence review, and Luna drafting through LangGraph.

The final recording is run `63584202-c4e4-4b55-84f9-3a5a530546b6`:
3 selected issues, 1 merged PR, 57 documentation files, 4 findings, **2 drafts
held for verification and 2 generated drafts**. Two earlier advisory runs are
also included. The final run completed without application or provider-call errors.

## Open the instance

The local recording is available at:

<http://127.0.0.1:8017/jev?run=63584202-c4e4-4b55-84f9-3a5a530546b6>

Start it again from the repository root:

```powershell
uv sync --project backend --locked
bun install --cwd frontend --frozen-lockfile
bun run --cwd frontend build
uv run --project backend --locked python experiments/serve_demo.py
```

The live launcher reads `MERGE_GATEWAY_API_KEY` or OpenCode's saved Merge
credential, and `GITHUB_TOKEN` or GitHub CLI authentication. NVIDIA retrieval uses
the optional `NVIDIA_*` settings in an ignored `.env` or `backend/.env` file.
Credentials are not stored in this recording or committed to the repository.

Click **Run live T3Code demo** to fetch the selected issues and PR again and run
the models. GitHub activity is live; implementation snippets use the pinned
commit in `experiments/t3code-demo.json`. Documentation citations record the
revision fetched during each run. Outcomes can change; none are fixed in code.

The checkbox **Hold unverified drafts in the next run** enables a narrow gate:
findings with Jev's `verify_implementation` recommendation do not enter the
drafting call. They remain visible, with Luna's original coverage assessment.
Other recommendations, including `retrieve_more`, remain advisory. Uncheck it
to run the advisory comparison.

The server binds only to `127.0.0.1`. Use the CLI runner when you want a full
artifact directory as well as a database record:

```powershell
uv run --project backend --locked python experiments/run_t3code.py --demo --hold-unverified
```

## Replay without credentials

This is a saved real run, not a new inference call:

```powershell
uv run --project backend --locked python experiments/import_recording.py
uv run --project backend --locked python experiments/serve_demo.py --replay
```

Build the frontend first. The live-run button is disabled in replay mode. The
importer preserves an existing run with the same ID.

The three `*-run.json` recordings retain classifications, distributions, excerpts, source
links, timings, usage, and the original generated drafts. Issue/PR bodies and
exact request envelopes are omitted from this portable recording. The original
local `experiments/results/<run-id>/` files retain the complete audit trail.

## Materials for the video

- [Retrospective and measured results](retrospective.md)
- [Recording script and shot list](video-script.md)
- [Source-reviewed T3Code patches](reviewed-docs/README.md)
- [Live case selection](../../experiments/t3code-demo.json)
- [Expanded OpenCode and Pi results and review dataset](cross-repository/README.md)
- [Editable Excalidraw architecture and evaluation walkthrough](explainer/README.md)

Jev's gate affects draft eligibility only when selected. It does not delete
findings, change Luna's coverage assessment, retry retrieval, or publish
documentation. Unavailable classifications fall back to manual-review advice;
the current gate does not hold them automatically. No upstream T3Code issues
or PRs were created by the experiment.
