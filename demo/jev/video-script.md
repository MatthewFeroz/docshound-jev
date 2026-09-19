# Recording guide: Jev inside a real documentation agent

Suggested title: **I added Jev to my LangGraph agent. Here's what actually happened.**

Target length: 5–7 minutes. Use the recorded run for the walkthrough, and clearly
label the live rerun separately. Do not show credentials or claim a replay is a
new inference run.

## Before recording

1. Open the gated run at <http://127.0.0.1:8017/jev?run=63584202-c4e4-4b55-84f9-3a5a530546b6>.
2. Keep this retrospective and the two reviewed patches available in the editor.
3. If recording live execution, click **Run live T3Code demo**. It uses the
   selected real issues and PR; completion time and model outputs may vary.
4. Inspect the page in your actual recording browser. Automated component tests,
   type checking, production build and API checks passed, but this session had
   no browser surface available for a visual check or screenshot capture.

## 0:00–0:35 — The problem

Show the demo's question and workflow.

> DocsHound looks at repository issues and shipped changes and proposes docs.
> But an issue isn't necessarily a documentation problem. Sometimes it's a bug,
> sometimes the answer is already documented, and sometimes retrieval found the
> wrong passage. I wanted Jev to classify those situations before I review a draft.

## 0:35–1:15 — Where Jev fits

Show the two green Jev steps, then `backend/app/langgraph_agent.py`.

> Luna still does the generative work. NVIDIA retrieves documentation. I added
> two LangGraph nodes: one classifies the request and whether the behavior is
> established; the other checks each retrieved passage and the documentation
> need. Jev returns fixed labels. Code turns those labels into a recommendation.

Show the optional hold checkbox. Explain that the earlier runs were advisory;
the selected recording enables the gate, while retaining Luna's coverage verdict
and every finding so disagreements remain inspectable.

## 1:15–2:00 — A useful limitation to document

Select **Provider-specific change request template support**. Expand the
implementation evidence and show the `provider.kind === "github"` condition.

> This is an open bug report, but the current limitation is verifiable. The code
> only detects templates for GitHub. Jev says current behavior is confirmed and
> identifies a missing limitation. It also wants better documentation evidence.
> Those are separate questions: an open product issue can still deserve docs.

Open the draft. Then show the shorter reviewed patch for #12330. Explain that
documenting a limitation does not implement support for GitLab or Azure DevOps.

## 2:00–2:45 — When not to invent an answer

Select **Cursor CLI configuration migration and startup failures**.

> The issue asks for migration behavior and better errors. We don't have a
> confirmed implementation here. Jev says verify the implementation first.
> In the first advisory run Luna declined to draft it. In the API rerun, Luna
> did draft it despite Jev's recommendation. With the gate enabled, this finding
> stays visible but doesn't enter the drafting call. That proves the gate works;
> it doesn't prove every held draft would have been wrong.

For comparison, open the advisory API run:
<http://127.0.0.1:8017/jev?run=3bf84bb0-e785-43e9-bd27-ecc383495373>.

Open a decision distribution. Call it model uncertainty, not accuracy.

## 2:45–3:30 — The retrieval problem

Select **Context-window indicator discoverability**. Expand a retrieved
excerpt, then the pinned Settings source snippet.

> The setting exists. But knowing that isn't the same as retrieving the right
> documentation passage. In an advisory run Jev recommended another search. In
> the gated run it was cautious about implementation readiness and held this
> draft too. The setting itself is evidenced, so this might be overcautious.
> That is the tradeoff I need to measure, not hide. Retrieval retries aren't
> implemented yet.

Show the reviewed #9352 patch: Settings → General → Legacy features.

## 3:30–4:10 — The positive drafting case

Select **export log records over OTLP** and open its draft.

> Here we have a merged PR, a relevant observability passage, and a specific
> configuration-precedence question. Jev recommends reviewing the draft and
> identifies the operator as its audience.

Show the existing documentation and PR links rather than asserting the whole
corpus lacks the answer based on one excerpt.

## 4:10–5:20 — What the experiment actually found

Show the retrospective metrics and raw context-indicator draft's "Resolution."

> Four findings, two drafts held, two drafts generated, eight Jev requests. The
> Jev calls cost about nine hundredths of a cent and took about half a second
> each. The gated run took 65 seconds. These are selected-case runs, not a benchmark.
>
> My first broad prompt mostly abstained. Smaller classification questions were
> more actionable, but I also supplied richer evidence and selected different
> cases, so this wasn't a controlled before-and-after comparison.
>
> I also found a problem after the model call: DocsHound copied a proposed fix
> from the issue into a section called Resolution. I removed that from the
> reviewed patch. A pre-draft classifier doesn't make the whole pipeline correct.

## 5:20–end — What comes next

Show the private fork or code diff and the two patch files.

> The working result is a classification layer that can hold a draft, plus two
> source-backed documentation proposals. Next I need independent labels, a
> fixed-input comparison with Luna alone, and a bounded retrieval retry. Only
> then can I claim Jev improves quality or saves work.

No upstream PR was published. The repository is private; change visibility
deliberately before advertising it as a public download.
