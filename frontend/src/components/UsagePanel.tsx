import type { UsageSummary } from "../types";

export function UsagePanel({ usage }: { usage?: UsageSummary | null }) {
  return (
    <section className="usage-panel" aria-label="Model usage">
      <h3>Model usage</h3>
      {!usage ? (
        <p>Usage was not recorded for this run.</p>
      ) : (
        <>
          <div className="usage-totals">
            <div>
              <strong>{usage.total_tokens.toLocaleString()}</strong>
              <span>Reported tokens</span>
            </div>
            <div>
              <strong>{usage.call_count}</strong>
              <span>Model calls</span>
            </div>
            <div>
              <strong>
                {usage.estimated_cost_usd == null
                  ? "Unpriced"
                  : `$${usage.estimated_cost_usd.toFixed(6)}`}
              </strong>
              <span>Estimated priced calls</span>
            </div>
          </div>
          <p>
            {usage.input_tokens.toLocaleString()} input ·{" "}
            {usage.output_tokens.toLocaleString()} output ·{" "}
            {usage.cached_input_tokens.toLocaleString()} cached input ·{" "}
            {usage.reasoning_tokens.toLocaleString()} reasoning tokens (included
            in output)
          </p>
          <p>
            {usage.pending_calls} pending · {usage.failed_calls} failed ·{" "}
            {usage.unpriced_calls} unpriced · {usage.calls_without_full_usage}{" "}
            with incomplete or unavailable usage
          </p>
          {usage.groups.length > 0 && (
            <details>
              <summary>By model and operation</summary>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Model / operation</th>
                      <th>Calls</th>
                      <th>Tokens</th>
                      <th>Estimate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usage.groups.map((group) => (
                      <tr
                        key={`${group.provider}/${group.model}/${group.operation}`}
                      >
                        <td>
                          {group.provider} / {group.model}
                          <br />
                          <small>{group.operation}</small>
                        </td>
                        <td>{group.call_count}</td>
                        <td>{group.total_tokens.toLocaleString()}</td>
                        <td>
                          {group.estimated_cost_usd == null
                            ? "Unpriced"
                            : `$${group.estimated_cost_usd.toFixed(6)}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </>
      )}
    </section>
  );
}
