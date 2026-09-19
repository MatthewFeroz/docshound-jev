# Show what Jev did, then test whether it helped

Open `docshound-jev.excalidraw` in Excalidraw using **Open** or by dropping the
file onto the canvas. It contains three editable 1920 x 1080 frames. Matching
SVG and PNG panels are included for slides and video editing. The previews
were rendered from the same geometry and visually inspected; the scene has
not been opened in the Excalidraw UI in this session.

## 1. Explain the architecture (about one minute)

Show **01 - Harness architecture**.

> Luna still drives the agent. It chooses the stage, identifies candidate
> findings, assesses documentation coverage and writes drafts. I added two
> explicit Jev nodes inside that existing LangGraph loop.

The actual graph edges in `backend/app/langgraph_agent.py` are:

```text
analyze     -> jev_triage -> llm_decide
search_docs -> jev_review -> llm_decide
```

`jev_triage` receives a finding and the matching original issue/PR text. It
classifies finding type, behavior readiness and audience. `jev_review` receives
the finding and the retrieved documentation excerpts. It classifies the
documentation need and each passage's relevance. It does not see Luna's
coverage verdict or a generated draft. Both can receive implementation
snippets, but none were manually supplied for the OpenCode/Pi collection.

Both call `typesafe/jev-1.13` through Merge's `/v1/decisions` endpoint. The
Python `recommend()` function in `backend/app/jev.py` combines the choices.
Inside `draft`, the opt-in gate excludes a finding when the recommendation is
`verify_implementation`, clears its draft fields, and records the hold. It
preserves the finding and Luna's coverage verdict.

There is no confidence threshold. `retrieve_more` does not cause a new search.
The `no_change` recommendation is advisory too; Luna's coverage independently
controls baseline drafting eligibility. Unavailable Jev outputs advise manual
review and do not automatically trigger this gate.

## 2. Show three concrete cases (about three minutes)

These examples were selected for explanation after seeing the results. They
are not a representative evaluation sample or preassigned correct answers.

**An intervention: Windows npm plugin entry-point URL handling.**

- [Open the run](http://127.0.0.1:8017/jev?run=599c2a8c-9825-4515-bf1c-2dfe54e7ab8d), then select that finding.
- [Open its full finding](http://127.0.0.1:8017/runs/599c2a8c-9825-4515-bf1c-2dfe54e7ab8d/findings/0).
- Source: OpenCode issue #38021. Show Luna's `partial` verdict, Jev's
  `needs_verification`, then the actual **Draft held** state.
- Say: "The gate changed what happened. To judge whether that was helpful,
  we need to establish whether the claimed behavior is implemented and whether
  useful documentation could already be written. The hold itself is not proof."

**A pass: separate provider and model settings.**

- In the same run, select **separate provider and model settings**.
- [Open its full finding and draft](http://127.0.0.1:8017/runs/599c2a8c-9825-4515-bf1c-2dfe54e7ab8d/findings/3).
- Source: merged OpenCode PR #49850. Show `confirmed`, `review_draft`, the
  retrieved configuration evidence and the generated draft.
- Say: "This passed. I still need to check the draft against the merged change
  and the existing docs; a merged PR does not by itself prove a docs gap."

**A redundant hold: agent-switching keyboard shortcuts after the v2 upgrade.**

- [Open the run](http://127.0.0.1:8017/jev?run=a9f14797-1929-439b-b69e-193e32c40e37), then select that finding.
- [Open its full finding](http://127.0.0.1:8017/runs/a9f14797-1929-439b-b69e-193e32c40e37/findings/7).
- Source: OpenCode issue #49133. Luna says `documented`, citing Tab and
  Shift+Tab behavior. Jev also marks a verification hold.
- Say: "Jev flagged this, but Luna already considered it ineligible for
  drafting. This flag added no extra prevention. I should not count it as a
  draft Jev saved us from."

Optional counterexample: return to the T3Code gated recording and show the
context-indicator hold. The supplied code establishes the setting, while the
generated question is broader. It illustrates possible overcaution, not a
human-labeled false positive.

## 3. Explain the numbers (about 45 seconds)

Show **02 - Measured outcomes**.

> Ten runs over 400 distinct source items produced 71 findings. Luna's coverage
> assessment made 52 eligible for drafting. Jev held 33 of those, leaving 19
> that were drafted. It also flagged 11 findings that Luna already would not
> draft. So 44 flags means 33 additional eligibility changes, not 44 proven
> bad drafts prevented.

The 142 Jev requests contained 497 classification questions, not 497 independent
examples. Jev reported $0.012280926 in cost. NVIDIA cost was not reported, so
do not call that the cost of the whole agent run.

## 4. Judge whether the decisions were good

Show **03 - Evaluate the decisions**.

The original dataset includes model outputs; looking at it is not a blind
review. `experiments/export_blind_review.py` prepares separate local packets
with those outputs hidden. Run it from the repository root:

```powershell
uv run --project backend --locked python experiments/export_blind_review.py
```

The prepared packets live in `experiments/results/blind-review/`. Review the
numbered Markdown files and fill `review-labels.jsonl` before opening
`answer-key.jsonl`. All labels start blank. The exporter refuses to overwrite
an existing review directory; use a new `--output` path for another reviewer.
If you have already seen a case's model verdict, record that prior exposure;
use another reviewer for a genuinely blinded judgment of the video examples.

First assess what is justified by the exact input packet. Record whether
behavior is established, documentation answers the question, and drafting is
justified. Allow **unknown**. Then, separately, inspect pinned source code and
full docs to establish stronger ground truth. Extra research can reveal why
the packet was insufficient without proving the input-only decision irrational.

For this dataset, review all 71 findings if practical: 33 newly held, 19 drafted,
and 19 already ineligible under Luna. Report separately:

- **Justified holds:** findings not ready for drafting based on reviewed evidence.
- **Unnecessary holds:** supported, useful documentation changes delayed by Jev.
- **Missed problems:** passed drafts with unsupported claims or unnecessary duplication.
- **Unknowns and overlap:** unresolved cases and decisions Luna already handled.

To claim that Jev actually prevented bad *draft text*, generate an advisory
baseline from the same frozen findings and evidence. Compare it with the
gated outputs under blinded review. A fresh GitHub scan changes the inputs and
is not that controlled comparison. The 33 held cases currently have no draft
text, so we cannot inspect hypothetical errors in those drafts.

The next engineering comparison should include Luna alone, a simple rule
(such as merged-PR metadata), and Jev on the same packets. Group related topics
when splitting development and evaluation data. Keep Pi's restricted docs
scope and the absence of supplied implementation snippets in the interpretation.

Close the video with: "The integration works. We can inspect exactly where it
changed the workflow. Whether the intervention improves documentation is the
question the review dataset is designed to answer."

## Source and format notes

Measured values come from `demo/jev/cross-repository/summary.json` and the saved
case records. Architecture follows `backend/app/langgraph_agent.py` and
`backend/app/jev.py`. The scene uses the official
[Excalidraw JSON format](https://docs.excalidraw.com/docs/codebase/json-schema).
Rebuild previews with:

```powershell
uv run --no-project --with pillow python experiments/create_jev_explainer.py
```
