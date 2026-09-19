import { useMemo, useState } from "react";
import type { RunEvent } from "../types";
import { ScrollArea } from "./ui/scroll-area";

const stages: Record<string, string> = {
  research: "Repository research",
  analyze: "Candidate analysis",
  search_docs: "Documentation search",
  draft: "Drafting",
  store: "Finalizing",
};

export function OperationInspector({ events }: { events: RunEvent[] }) {
  const [query, setQuery] = useState("");
  const [onlyErrors, setOnlyErrors] = useState(false);
  const spans = useMemo(() => {
    const merged = new Map<string, RunEvent>();
    for (const event of events)
      if (event.span_id) {
        merged.set(event.span_id, { ...merged.get(event.span_id), ...event });
      }
    return [...merged.values()];
  }, [events]);
  const filtered = spans.filter(
    (span) =>
      (!onlyErrors || span.status === "error") &&
      [span.label, span.name, span.stage, span.output_summary, span.error]
        .join(" ")
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const groups = new Map<string, RunEvent[]>();
  for (const span of filtered) {
    const stage = span.stage || "other";
    groups.set(stage, [...(groups.get(stage) ?? []), span]);
  }
  const running = spans.filter((span) => span.status === "running").length;
  const failed = spans.filter((span) => span.status === "error").length;
  return (
    <section className="operation-inspector" aria-label="Operation inspector">
      <div className="inspector-heading">
        <h3>Operation inspector</h3>
        <span>
          {spans.length} calls · {running} active
        </span>
      </div>
      <div className="operation-filters">
        <input
          aria-label="Search operations"
          placeholder="Search operations…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button
          type="button"
          aria-pressed={onlyErrors}
          onClick={() => setOnlyErrors(!onlyErrors)}
        >
          Errors {failed}
        </button>
      </div>
      <ScrollArea
        className="operations-scroll"
        viewportProps={{ "aria-label": "Operations" }}
      >
        {filtered.length === 0 && (
          <p className="inspector-empty">
            {spans.length
              ? "No matching operations."
              : "Operations will appear when the agent starts."}
          </p>
        )}
        {[...groups].map(([stage, items]) => (
          <section key={stage} className="operation-stage">
            <h4>
              {stages[stage] || stage.replaceAll("_", " ")}{" "}
              <span>{items.length}</span>
            </h4>
            {items.map((span) => (
              <details
                key={span.span_id}
                className={`operation-row operation-${span.status}`}
              >
                <summary>
                  <span className="operation-title">
                    <i
                      className={`operation-dot is-${span.status}`}
                      aria-hidden="true"
                    />
                    {span.label || span.name}
                  </span>
                  <small>
                    {span.duration_ms != null
                      ? span.duration_ms >= 1000
                        ? `${(span.duration_ms / 1000).toFixed(1)} s`
                        : `${span.duration_ms.toFixed(0)} ms`
                      : span.progress_total
                        ? `${span.progress_current ?? 0}/${span.progress_total}`
                        : "Running"}
                  </small>
                </summary>
                <p>
                  {span.output_summary ||
                    span.progress_detail ||
                    span.input_summary}
                </p>
                {span.error && (
                  <p className="operation-error" role="alert">
                    {span.error}
                  </p>
                )}
                {span.status === "running" && !!span.progress_total && (
                  <progress
                    aria-label="Operation progress"
                    max={span.progress_total}
                    value={span.progress_current ?? 0}
                  />
                )}
                <div className="operation-payloads">
                  {span.input_details && (
                    <>
                      <h5>Inputs</h5>
                      <pre>{JSON.stringify(span.input_details, null, 2)}</pre>
                    </>
                  )}
                  {span.output_details && (
                    <>
                      <h5>Results</h5>
                      <pre>{JSON.stringify(span.output_details, null, 2)}</pre>
                    </>
                  )}
                </div>
                <dl className="trace-identifiers">
                  <dt>Trace</dt>
                  <dd>
                    <code>{span.trace_id || "Unavailable"}</code>
                  </dd>
                  <dt>Span</dt>
                  <dd>
                    <code>{span.span_id}</code>
                  </dd>
                </dl>
              </details>
            ))}
          </section>
        ))}
      </ScrollArea>
    </section>
  );
}
