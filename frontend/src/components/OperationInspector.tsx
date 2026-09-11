import type { RunEvent } from "../types";

export function OperationInspector({ events }: { events: RunEvent[] }) {
  const spans = new Map<string, RunEvent>();
  for (const event of events) {
    if (event.span_id)
      spans.set(event.span_id, { ...spans.get(event.span_id), ...event });
  }
  if (!spans.size) return null;
  return (
    <section className="operation-inspector" aria-label="Operation inspector">
      <h3>Operation inspector</h3>
      {[...spans.values()].map((span) => (
        <details
          key={span.span_id}
          className={`operation-row operation-${span.status}`}
        >
          <summary>
            <span>
              {span.status === "success"
                ? "✓"
                : span.status === "error"
                  ? "!"
                  : "◌"}{" "}
              {span.label || span.name}
            </span>
            <small>
              {span.duration_ms != null
                ? `${span.duration_ms.toFixed(0)} ms`
                : span.progress_total
                  ? `${span.progress_current ?? 0}/${span.progress_total}`
                  : "Running"}
            </small>
          </summary>
          <p>
            {span.output_summary || span.progress_detail || span.input_summary}
          </p>
          {span.error && <p role="alert">{span.error}</p>}
          <dl>
            <dt>Stage</dt>
            <dd>{span.stage}</dd>
            <dt>Trace</dt>
            <dd>
              <code>{span.trace_id}</code>
            </dd>
            <dt>Span</dt>
            <dd>
              <code>{span.span_id}</code>
            </dd>
          </dl>
          {span.input_details && (
            <>
              <h4>Inputs</h4>
              <pre>{JSON.stringify(span.input_details, null, 2)}</pre>
            </>
          )}
          {span.output_details && (
            <>
              <h4>Results</h4>
              <pre>{JSON.stringify(span.output_details, null, 2)}</pre>
            </>
          )}
        </details>
      ))}
    </section>
  );
}
