import type { GapCluster, JevAnswer } from "../types";

export function readable(value: string) {
  return value.replaceAll("_", " ");
}

export const recommendations: Record<string, string> = {
  review_draft: "Review the documentation draft",
  verify_implementation: "Verify the implementation first",
  retrieve_more: "Retrieve more evidence",
  no_change: "Existing documentation answers this",
  manual_review: "Review manually",
};

function Classification({ name, answer }: { name: string; answer: JevAnswer }) {
  return (
    <div className="jev-classification">
      <span>{readable(name)}</span>
      <strong>{readable(answer.choice)}</strong>
      <details>
        <summary>Decision distribution</summary>
        {Object.entries(answer.probabilities).map(([key, probability]) => (
          <div className="jev-probability" key={key}>
            <span>{readable(key)}</span>
            <progress max={1} value={probability} />
            <span>{Math.round(probability * 100)}%</span>
          </div>
        ))}
      </details>
    </div>
  );
}

export function JevAssessment({ cluster }: { cluster: GapCluster }) {
  const triage = cluster.jev_triage;
  const review = cluster.jev_assessment;
  if (!triage && !review) return null;
  const advice = review?.recommendation || "manual_review";
  return (
    <section className="jev-assessment" aria-label="Jev assessment">
      <div className="jev-panel-heading">
        <span className="jev-wordmark">JEV</span>
        <span>CLASSIFICATION & EVIDENCE</span>
        <span className="jev-shadow">Advisory</span>
      </div>
      <h3>{recommendations[advice] || readable(advice)}</h3>
      <p className="jev-muted">
        Jev recommends a review step. Luna's drafting decision remains visible
        for comparison.
      </p>
      {(triage?.status !== "succeeded" || review?.status !== "succeeded") && (
        <p role="status">
          Some classifications are unavailable. Check the run trace; this is not
          a negative verdict.
        </p>
      )}
      <div className="jev-classifications">
        {Object.entries(triage?.answers || {}).map(([key, answer]) => (
          <Classification key={key} name={key} answer={answer} />
        ))}
        {review?.answers?.gap_kind && (
          <Classification
            name="documentation need"
            answer={review.answers.gap_kind}
          />
        )}
      </div>
      <h4>Did retrieval answer the question?</h4>
      <div className="jev-evidence-list">
        {(review?.documents || []).map((document, index) => (
          <details key={`${document.path}-${index}`} className="jev-evidence">
            <summary>
              <span>{document.path}</span>
              <strong
                className={`jev-tag jev-tag-${document.answer?.choice || "uncertain"}`}
              >
                {readable(document.answer?.choice || "unavailable")}
              </strong>
            </summary>
            <p>
              {cluster.documentation_evidence?.[index]?.content ||
                "Excerpt not saved."}
            </p>
            <a href={document.url} target="_blank" rel="noreferrer">
              Open source document ↗
            </a>
          </details>
        ))}
      </div>
      {!!cluster.implementation_evidence?.length && (
        <details className="jev-source-code">
          <summary>
            Implementation evidence · {cluster.implementation_evidence.length}{" "}
            pinned snippets
          </summary>
          {cluster.implementation_evidence.map((source, index) => (
            <div key={`${source.path}-${index}`}>
              <a href={source.url} target="_blank" rel="noreferrer">
                {source.path} ↗
              </a>
              <pre>{source.content}</pre>
            </div>
          ))}
        </details>
      )}
      <p className="jev-footnote">
        Distributions describe the model's judgment, not measured accuracy. No
        human verdict has been assigned.
      </p>
    </section>
  );
}
