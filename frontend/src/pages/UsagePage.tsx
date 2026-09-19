import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { BrandHeader } from "../components/BrandHeader";
import { UsagePanel } from "../components/UsagePanel";
import type { UsageHistory } from "../types";

export function UsagePage() {
  const [history, setHistory] = useState<UsageHistory | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    void api
      .getUsage()
      .then(setHistory)
      .catch((error) => setError(String(error)));
  }, []);
  return (
    <>
      <BrandHeader suffix="usage">
        <Link to="/">New scan</Link>
      </BrandHeader>
      <main className="usage-history">
        <h2>Usage and scan history</h2>
        <p>
          Most recent 500 runs. Costs cover provider-reported or estimated
          priced calls only; unavailable usage and unknown prices are shown
          explicitly.
        </p>
        {error && <p role="alert">{error}</p>}
        {history ? (
          <>
            <UsagePanel usage={history.summary} />
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Status</th>
                    <th>Tokens</th>
                    <th>Known cost</th>
                  </tr>
                </thead>
                <tbody>
                  {history.runs.map((run) => (
                    <tr key={run.run_id}>
                      <td>
                        <Link to={`/?run=${run.run_id}`}>{run.repo}</Link>
                        <br />
                        <small>
                          {new Date(run.started_at).toLocaleString()}
                        </small>
                      </td>
                      <td>{run.status.replaceAll("_", " ")}</td>
                      <td>
                        {run.usage?.total_tokens.toLocaleString() ??
                          "Not recorded"}
                      </td>
                      <td>
                        {(run.usage?.cost_usd ??
                          run.usage?.estimated_cost_usd) == null
                          ? "Unpriced"
                          : `$${(run.usage?.cost_usd ?? run.usage?.estimated_cost_usd)?.toFixed(6)}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {history.runs.length === 0 && <p>No saved runs yet.</p>}
          </>
        ) : (
          !error && <p>Loading usage…</p>
        )}
      </main>
    </>
  );
}
