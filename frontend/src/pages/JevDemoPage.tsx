import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { BrandHeader } from "../components/BrandHeader";
import {
  JevAssessment,
  readable,
  recommendations,
} from "../components/JevAssessment";
import { OperationInspector } from "../components/OperationInspector";
import type { Run } from "../types";
import "./jev-demo.css";

const steps = [
  ["research", "GitHub", "Collect evidence"],
  ["analyze", "Luna", "Identify findings"],
  ["jev_triage", "Jev", "Classify the need"],
  ["search_docs", "NVIDIA + Luna", "Retrieve & assess"],
  ["jev_review", "Jev", "Check the evidence"],
  ["draft", "Luna", "Draft for review"],
];

export function JevDemoPage() {
  const [params, setParams] = useSearchParams();
  const [run, setRun] = useState<Run | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [holdUnverified, setHoldUnverified] = useState(true);
  const runId = params.get("run");

  useEffect(() => {
    let active = true;
    Promise.all([api.listRuns(), api.getJevDemo()])
      .then(([items, demo]) => {
        if (!active) return;
        const available = items.filter(
          (item) =>
            item.jev_gate_enabled ||
            item.top_gaps.some((gap) => gap.jev_triage || gap.jev_assessment),
        );
        setRuns(available);
        setEnabled(demo.enabled);
        if (!runId && available.length)
          setParams({ run: available[0].run_id }, { replace: true });
      })
      .catch((e) => active && setError(String(e)));
    return () => {
      active = false;
    };
  }, [runId, setParams]);

  useEffect(() => {
    if (!runId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    setSelected(0);
    setRun(null);
    const refresh = async () => {
      try {
        const latest = await api.getRun(runId);
        if (!active) return;
        setRun(latest);
        if (latest.status === "running") timer = setTimeout(refresh, 1500);
      } catch (e) {
        if (active) setError(String(e));
      }
    };
    void refresh();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [runId]);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const created = await api.runJevDemo(holdUnverified);
      setParams({ run: created.run_id });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const findings = run?.top_gaps || [];
  const finding = findings[selected];
  const jevResults = findings
    .flatMap((f) => [f.jev_triage, f.jev_assessment])
    .filter(Boolean);
  const jevCost = jevResults.reduce(
    (sum, result) => sum + (result?.usage?.cost || 0),
    0,
  );
  const running = run?.status === "running";
  const events = run?.operation_events || [];

  return (
    <>
      <BrandHeader
        suffix="Jev Lab"
        tagline="Jev decisions across real documentation runs"
      >
        <nav className="topnav">
          <Link className="published-link" to="/">
            DocsHound
          </Link>
          <Link className="published-link" to="/usage">
            Usage
          </Link>
        </nav>
      </BrandHeader>
      <main className="jev-demo">
        <section className="jev-hero">
          <div>
            <div className="jev-eyebrow">
              DOCSHOUND × TYPESAFE · {run?.repo || "REPOSITORY EXPERIMENTS"}
            </div>
            <h1>
              Documentation gap.
              <br />
              <em>Or a different problem?</em>
            </h1>
            <p>
              Luna investigates and writes. NVIDIA retrieves. Jev classifies the
              request and checks the evidence before a draft is reviewed.
            </p>
          </div>
          <div className="jev-run-controls">
            <label className="jev-gate-option">
              <input
                type="checkbox"
                checked={holdUnverified}
                onChange={(event) => setHoldUnverified(event.target.checked)}
              />
              Hold unverified drafts in the next run
            </label>
            <button
              className="publish-btn"
              disabled={!enabled || busy || running}
              onClick={start}
            >
              {busy
                ? "Fetching source evidence…"
                : running
                  ? "Agent is running…"
                  : "Run live T3Code demo →"}
            </button>
            <span>3 selected issues · 1 merged PR · live model calls</span>
            <label>
              Recorded runs
              <select
                value={runId || ""}
                onChange={(e) => setParams({ run: e.target.value })}
              >
                <option value="" disabled>
                  Select a run
                </option>
                {runs.map((item) => (
                  <option key={item.run_id} value={item.run_id}>
                    {item.repo} · {item.run_id.slice(0, 8)} ·{" "}
                    {item.clusters_found} findings · {item.status}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </section>
        {error && (
          <p className="pr-alert" role="alert">
            {error}
          </p>
        )}
        <section className="jev-pipeline" aria-label="LangGraph workflow">
          {steps.map(([stage, owner, label], i) => {
            const activity = events.filter(
              (e) => e.stage === stage && e.type.startsWith("stage_"),
            );
            const latest = activity.at(-1);
            return (
              <div
                className={`${owner === "Jev" ? "jev-step-special" : ""} ${latest?.type === "stage_completed" ? "jev-step-done" : latest ? "jev-step-running" : ""}`}
                key={stage}
              >
                <span>
                  {String(i + 1).padStart(2, "0")} · {owner}
                </span>
                <strong>{label}</strong>
                <small>
                  {latest?.type === "stage_completed"
                    ? "Complete"
                    : latest
                      ? "Running"
                      : "Waiting"}
                </small>
              </div>
            );
          })}
        </section>
        <section className="jev-metrics" aria-label="Run results">
          <div>
            <strong>{findings.length}</strong>
            <span>findings classified</span>
          </div>
          <div>
            <strong>{run?.docs_candidates_inspected || 0}</strong>
            <span>documentation files</span>
          </div>
          <div>
            <strong>{findings.filter((f) => f.draft_markdown).length}</strong>
            <span>drafts to review</span>
          </div>
          <div>
            <strong>${jevCost.toFixed(5)}</strong>
            <span>reported Jev cost</span>
          </div>
        </section>
        {run && (
          <p className="jev-mode">
            {run.jev_gate_enabled
              ? `Draft gate enabled · ${findings.filter((f) => f.jev_draft_hold).length} findings held for verification`
              : "Advisory run · Jev did not block drafts"}
          </p>
        )}
        {running && (
          <p role="status" className="jev-running">
            Live run in progress. The workflow above updates as each stage
            completes.
          </p>
        )}
        {!!run?.errors.length && (
          <p className="pr-alert">{run.errors.join(" · ")}</p>
        )}
        {!!findings.length && (
          <section className="jev-workspace">
            <aside className="jev-finding-list" aria-label="Findings">
              <h2>The findings</h2>
              {findings.map((item, index) => (
                <button
                  key={index}
                  aria-pressed={selected === index}
                  onClick={() => setSelected(index)}
                >
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{item.name}</strong>
                  <small>
                    {recommendations[
                      item.jev_assessment?.recommendation || ""
                    ] || "Earlier experiment"}
                  </small>
                </button>
              ))}
            </aside>
            {finding && (
              <article className="jev-finding-detail">
                <div className="jev-eyebrow">
                  FINDING {selected + 1} · {readable(finding.finding_type)}
                </div>
                <h2>{finding.name}</h2>
                <p className="jev-question">{finding.recurring_question}</p>
                <div className="jev-source-links">
                  {[...finding.issue_refs, ...finding.pr_refs].map((ref) => (
                    <a
                      key={ref}
                      href={`https://github.com/${ref.replace("#", "/issues/")}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      #{ref.split("#")[1]} ↗
                    </a>
                  ))}
                </div>
                <JevAssessment cluster={finding} />
                <section className="jev-luna">
                  <div className="review-label">LUNA'S COVERAGE ASSESSMENT</div>
                  <h3>
                    {readable(
                      finding.documentation_coverage?.status || "unknown",
                    )}
                  </h3>
                  <p>{finding.documentation_coverage?.rationale}</p>
                  <Link
                    className="publish-btn"
                    to={`/runs/${runId}/findings/${selected}`}
                  >
                    {finding.draft_markdown
                      ? "Open the draft & source evidence →"
                      : "Inspect the finding →"}
                  </Link>
                </section>
              </article>
            )}
          </section>
        )}
        {!run && !error && <p>Select a recorded run or start a live demo.</p>}
        <details className="jev-trace">
          <summary>Inspect the complete agent trace</summary>
          <OperationInspector events={events} />
        </details>
        <p className="jev-footnote">
          Selected real cases, not a benchmark. The optional gate holds findings
          that need implementation verification; retrieval recommendations
          remain advisory. Classification confidence is not measured accuracy.
        </p>
      </main>
    </>
  );
}
