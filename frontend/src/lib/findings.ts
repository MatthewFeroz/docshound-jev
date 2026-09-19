import type { GapCluster } from "../types";

// Keep the original array index for links and approvals; excluded records remain auditable.
export function isDocumentationProposal(cluster: GapCluster): boolean {
  const coverage = cluster.documentation_coverage;
  return (
    !cluster.jev_draft_hold &&
    cluster.review_status !== "no_change_needed" &&
    (!coverage ||
      ((coverage.status === "missing" || coverage.status === "partial") &&
        coverage.recommended_action !== "no_change"))
  );
}
