import { useState } from "react";
import type { UsageSummary, UsageTotals } from "../types";
import { ScrollArea } from "./ui/scroll-area";

const money = (amount: number | null | undefined) =>
  amount == null ? "Unpriced" : `$${amount.toFixed(6)}`;
const cost = (usage: UsageTotals) => usage.cost_usd ?? usage.estimated_cost_usd;
const label = (value: string) => value.replaceAll("_", " ");
type Metric = "total_tokens" | "input_tokens" | "output_tokens";

export function UsagePanel({ usage }: { usage?: UsageSummary | null }) {
  const [metric, setMetric] = useState<Metric>("total_tokens");
  const [selected, setSelected] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const calls = usage?.calls ?? [];
  const active = calls.find((call) => call.call_id === selected);
  const maximum = Math.max(1, ...calls.map((call) => call[metric] ?? 0));
  return (
    <section className="usage-panel" aria-label="Model usage">
      <div className="inspector-heading">
        <h3>Model usage</h3>
        {usage && (
          <span className={usage.pending_calls ? "usage-live" : ""}>
            {usage.pending_calls
              ? `${usage.pending_calls} in flight`
              : `${usage.call_count} calls`}
          </span>
        )}
      </div>
      {!usage ? (
        <p>Usage was not recorded for this run.</p>
      ) : (
        <>
          <div className="usage-totals">
            <button
              type="button"
              className="token-counter"
              aria-expanded={expanded}
              onClick={() => setExpanded(!expanded)}
            >
              <strong>{usage[metric].toLocaleString()}</strong>
              <span>
                {metric === "total_tokens"
                  ? "Reported tokens"
                  : metric === "input_tokens"
                    ? "Input tokens"
                    : "Output tokens"}{" "}
                ↗
              </span>
            </button>
            <div>
              <strong>{money(cost(usage))}</strong>
              <span>
                {cost(usage) == null
                  ? "Pricing unavailable"
                  : (usage.reported_cost_calls ?? 0) > 0
                    ? (usage.estimated_cost_calls ?? 0) > 0
                      ? "Reported + estimated cost"
                      : "Provider-reported cost"
                    : "Estimated priced calls"}
              </span>
            </div>
          </div>
          <button
            type="button"
            className="usage-expand"
            aria-expanded={expanded}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "Hide" : "Explore"} token usage
          </button>
          <p className="usage-completeness">
            {usage.pending_calls} pending · {usage.failed_calls} failed ·{" "}
            {usage.unpriced_calls} unpriced · {usage.calls_without_full_usage}{" "}
            with incomplete or unavailable usage
          </p>
          {expanded && (
            <div className="usage-explorer">
              <div className="usage-metrics" aria-label="Token metric">
                {(
                  ["total_tokens", "input_tokens", "output_tokens"] as const
                ).map((key) => (
                  <button
                    type="button"
                    key={key}
                    aria-pressed={metric === key}
                    onClick={() => setMetric(key)}
                  >
                    {key === "total_tokens"
                      ? "All tokens"
                      : key === "input_tokens"
                        ? "Input"
                        : "Output"}
                  </button>
                ))}
              </div>
              <p>
                Updates after each provider response. Select a call to inspect
                it.
              </p>
              {calls.length > 0 ? (
                <>
                  <div
                    className="usage-chart"
                    role="group"
                    aria-label="Tokens by model call"
                  >
                    {calls.map((call, index) => (
                      <button
                        type="button"
                        key={call.call_id}
                        aria-pressed={selected === call.call_id}
                        aria-label={`Call ${index + 1}: ${call.model}, ${label(call.operation)}, ${call[metric] ?? "unknown"} tokens`}
                        title={`${call.model} · ${label(call.operation)}`}
                        className={`usage-bar is-${call.request_status}`}
                        onClick={() =>
                          setSelected(
                            selected === call.call_id ? null : call.call_id,
                          )
                        }
                      >
                        <span
                          style={{
                            height: `${Math.max(4, ((call[metric] ?? 0) / maximum) * 100)}%`,
                          }}
                        />
                      </button>
                    ))}
                  </div>
                  {active && (
                    <div className="usage-call-detail" role="status">
                      <strong>{active.model}</strong>
                      <span>
                        {label(active.operation)} · {active.request_status}
                        {active.duration_ms != null
                          ? ` · ${(active.duration_ms / 1000).toFixed(1)} s`
                          : ""}
                      </span>
                      <span>
                        {active.input_tokens?.toLocaleString() ?? "?"} input ·{" "}
                        {active.output_tokens?.toLocaleString() ?? "?"} output
                      </span>
                      <span>
                        {money(
                          active.reported_cost_usd ?? active.estimated_cost_usd,
                        )}{" "}
                        ·{" "}
                        {active.cost_source
                          ? label(active.cost_source)
                          : "pricing unavailable"}
                      </span>
                    </div>
                  )}
                </>
              ) : (
                <p>Per-call history is unavailable for this older run.</p>
              )}
              <div className="token-breakdown">
                <span>
                  Input <strong>{usage.input_tokens.toLocaleString()}</strong>
                </span>
                <span>
                  Output <strong>{usage.output_tokens.toLocaleString()}</strong>
                </span>
                <span>
                  Cached input{" "}
                  <strong>{usage.cached_input_tokens.toLocaleString()}</strong>
                </span>
                <span>
                  Reasoning{" "}
                  <strong>{usage.reasoning_tokens.toLocaleString()}</strong>
                </span>
              </div>
              <p>
                Cached tokens are included in input; reasoning tokens are
                included in output.
              </p>
              {usage.groups.length > 0 && (
                <details className="usage-models">
                  <summary>By model and operation</summary>
                  <ScrollArea className="usage-groups-scroll">
                    {usage.groups.map((group) => (
                      <div
                        className="usage-group"
                        key={`${group.provider}/${group.model}/${group.operation}`}
                      >
                        <div>
                          <strong>{group.model}</strong>
                          <small>
                            {label(group.operation)} · {group.call_count} calls
                          </small>
                        </div>
                        <div>
                          <strong>{group[metric].toLocaleString()}</strong>
                          <small>{money(cost(group))}</small>
                        </div>
                      </div>
                    ))}
                  </ScrollArea>
                </details>
              )}
              <p className="usage-price-note">
                Merge costs come from <code>usage.cost</code> for the served
                route. Direct API costs use a saved rate-card estimate. Unpriced
                calls are excluded; this is not an invoice total.
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
