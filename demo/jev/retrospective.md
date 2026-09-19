# What Jev actually did in DocsHound

## The question

Can a small decision model tell a documentation agent whether a finding needs
documentation, implementation verification, or better evidence?

This is an integration experiment with selected real cases, followed by an
optional drafting gate. It is not an accuracy benchmark, a cost-saving
experiment, or a demonstration of autonomous documentation publication.

## First attempt: one broad question

The first run examined 50 issues, 50 merged PRs and 57 documentation files.
Luna produced eight findings and four drafts. Jev's broad pre-draft support
check returned seven `insufficient_evidence` verdicts and one `supported_gap`.
The eight checks cost $0.00063084 according to Merge's response usage.

Those abstentions were not seven detected false findings. The initial Jev input
contained finding summaries and short documentation excerpts, without the
original issue bodies or implementation evidence. It was poorly equipped to
establish whether a proposed behavior was actually implemented.

## Second attempt: separate the decisions

Run: `b39d064e-d8a5-444e-a40c-0fc7f70e1ad2`.
UTC start: 2026-09-19. Local date: 2026-09-18 in New York.
Implementation and retrieved documentation revision:
`9cb586acd0494c4f47f60045ee42ef25edb5a07c`.

The selected inputs were issues #9352, #12330 and #12451, plus merged PR #12493.
They were selected after source inspection to exercise different decisions;
they are not a random or held-out sample.

The graph adds two explicit nodes:

```mermaid
flowchart LR
  A[GitHub research] --> B[Luna: identify findings]
  B --> C[Jev: classify request, readiness, audience]
  C --> D[NVIDIA retrieval + Luna coverage]
  D --> E[Jev: classify each passage and documentation need]
  E --> F[Luna: draft for review]
```

Triage sees original issue/PR text and source-code excerpts matched to the
finding. Evidence review sees the finding, each retrieved excerpt and any
implementation evidence. It does not see Luna's coverage verdict, generated
draft, or subsequent review outcome. Questions over the same input are batched
in one request; code combines the answers into an advisory recommendation.

| Case | Jev readiness | Documentation need | Recommendation | Luna output |
|---|---|---|---|---|
| [Cursor migration #12451](https://github.com/pingdotgg/t3code/issues/12451) | Needs verification | Missing procedure | Verify implementation | No draft; coverage unverified |
| [OTLP logs PR #12493](https://github.com/pingdotgg/t3code/pull/12493) | Confirmed | Unclear configuration | Review draft | Configuration-precedence draft |
| [Template support #12330](https://github.com/pingdotgg/t3code/issues/12330) | Confirmed | Missing limitation | Retrieve more | GitHub-only limitation draft |
| [Context indicator #9352](https://github.com/pingdotgg/t3code/issues/9352) | Confirmed | Unclear configuration | Retrieve more | Opt-in setting draft |

Jev classified the primary need in the three issues as `product_bug`, despite
two having explainable current behavior. The classifications were not uniformly
decisive: for template support, product bug, documentation and mixed all had
substantial probability. This supports keeping request type and documentation
readiness separate instead of dropping every issue labeled "bug."

## Measured result

- 3 issues and 1 merged PR fetched; 57 documentation files inspected.
- 4 findings, 3 generated review drafts, 0 run errors and 0 failed model calls.
- 8 Jev requests: 4 triage and 4 evidence-review requests, containing 28 questions.
- Jev classified 11 of 12 retrieved passages as unrelated, and one as useful
  background. These are predictions, not validated relevance labels.
- Jev's provider-reported cost: **$0.000859068** for the eight requests.
- Median end-to-end duration of each Jev helper call: **501.7 ms**. The usage
  tracker, which excludes some client setup, reports a median of 462.4 ms.
- End-to-end agent run: **76.2 seconds**.
- Reported Merge cost across Luna and Jev: **$0.014879868**. NVIDIA's 25 calls
  had no price in the usage record, so this is not the full run's total cost.

There were no independently assigned human labels. We cannot report precision,
recall, accuracy, time saved, or prevented bad drafts. Luna already deferred the
Cursor case on its own. This run does not show that Jev improved that decision.

## What was useful

The model outputs produced distinct, inspectable work queues. "Needs more
evidence" became either verify the implementation or examine the retrieved
passages. The source-code evidence established that the context indicator still
exists and that template discovery is GitHub-only at the recorded commit.

The generated drafts also yielded two concrete, agent-reviewed documentation
patches: explain how to enable the indicator, and state the template support
limitation. Both pass `git apply --check` against the recorded T3Code checkout.
They remain proposed changes, not maintainer-approved documentation.

## What did not work cleanly

1. **Relevance may be too strict.** Eleven unrelated labels out of twelve need
   independent review. A broad source-control page can be useful background even
   if it does not answer a specific template-support question. Short retrieved
   chunks also differ from the full pages. Do not treat these labels as proof of
   a retrieval defect or automatically discard their parent documents.
2. **Readiness is not publication approval.** A source snippet establishes a
   narrow behavior, not every provider, release or client. The reviewed patches
   avoid claiming the requested product fixes have shipped.
3. **Draft postprocessing can reintroduce unsupported claims.** The raw context
   indicator draft correctly describes opt-in behavior, then DocsHound appends
   an issue's requested default-on change under "Resolution." The proposed fix
   is not a verified resolution. The raw output remains in the recording; the
   reviewed patch removes that section. This is a concrete follow-up for
   DocsHound's workaround extraction, independent of Jev's pre-draft checks.
4. **This advisory run measured no automatic intervention.** Recommendations were advisory.
   The agent did not perform a second retrieval because Jev requested it, and
   Jev did not reduce the number of drafts. The follow-up below tests a gate.

## Follow-up: the recommendation became an actual gate

A second advisory run was started through the running app's API:
`3bf84bb0-e785-43e9-bd27-ecc383495373`. It completed with four findings and four
drafts. Jev again recommended verifying the Cursor migration, but this time
Luna drafted it. The draft said no migration procedure was confirmed; DocsHound
then appended the issue author's migration instructions under "Resolution."
That contradiction makes the need for review visible. It is not evidence that
the reported workaround itself is false.

We then added an opt-in gate with a simple rule: hold a finding before drafting
when its Jev recommendation is `verify_implementation`. The classification
remains saved alongside the unchanged Luna coverage verdict. Held findings
remain visible and cannot be approved as documentation proposals through the
existing approval endpoint. `retrieve_more` does not yet trigger another search.

Final run: `63584202-c4e4-4b55-84f9-3a5a530546b6`, using the same selected issue/PR
IDs and pinned implementation evidence. The LLM-generated findings differ in
wording across runs; this is not a fixed-input controlled comparison.

| Measure | Advisory CLI | Advisory API | Gate enabled |
|---|---:|---:|---:|
| Findings | 4 | 4 | 4 |
| Generated drafts | 3 | 4 | 2 |
| Findings held by Jev gate | 0 | 0 | 2 |
| Jev requests | 8 | 8 | 8 |
| Reported Jev cost | $0.000859068 | $0.00086478 | $0.000870702 |

In the gated run, Luna marked all four findings `partial`. The gate held the
Cursor migration and context-indicator findings, and passed OTLP logging and
template support to drafting. The trace and saved states verify that only the
two passed findings reached `draft_review_documents`. The run took **65.4
seconds**; median end-to-end Jev helper duration was **458.95 ms**. Reported
Merge cost was $0.011784102; NVIDIA pricing remains unavailable.

The context-indicator hold exposes the tradeoff: source snippets establish the
setting, yet Jev's readiness choice changed to `needs_verification` with 0.63
probability when judging the generated question about main and worktree threads.
The existing simple gate acts on the selected label, not a calibrated threshold.
This may withhold useful documentation. We preserved it instead of tuning or
rerunning until the preferred verdict appeared.

**The observable result is two withheld drafts, not two proven bad drafts
prevented.** The earlier notes about advisory behavior refer to the first two
selected-case runs. The final run demonstrates actual draft gating; independent
quality and savings measurements are still absent.

## What to evaluate next

Independently label finding readiness and passage relevance across additional
repositories. Split related topics together so nearly identical runs cannot
appear in both tuning and evaluation data. Compare Luna alone, simple metadata
rules, and Luna plus Jev on the same frozen evidence. Evaluate the optional hold
for useful drafts incorrectly deferred, calibrate its policy, and test a bounded
retrieval retry separately before treating either as a production default.

The supported takeaway is narrow: **Jev works as an inexpensive typed
classification layer inside this LangGraph workflow, and its separate outputs
can drive an inspectable draft hold. Its incremental quality benefit is still
unproven.**
