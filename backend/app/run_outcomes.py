from app.state import AgentState, RunOutcome


def apply_run_outcome(state: AgentState) -> None:
    """Attach the user-facing terminal outcome to an agent run."""
    state.outcome, state.summary = resolve_run_outcome(state)


def resolve_run_outcome(state: AgentState) -> tuple[RunOutcome, str]:
    if state.status == "running":
        return "in_progress", "Run is in progress."

    if state.status == "failed":
        return "failed", "The run could not be completed."

    if (
        state.errors
        or state.status == "completed_with_errors"
        or any(
            source.source_type in {"repository_docs_error", "official_docs_error"}
            for source in state.docs_sources
        )
    ):
        return (
            "partial_failure",
            "The run completed with errors, so its recommendations may be incomplete.",
        )

    coverage_unverified = sum(
        cluster.documentation_coverage is not None
        and cluster.documentation_coverage.status == "unable_to_verify"
        for cluster in state.clusters
    )
    if coverage_unverified:
        proposals = sum(cluster.is_documentation_proposal for cluster in state.clusters)
        ready = (
            f"{proposals} documentation proposal{' is' if proposals == 1 else 's are'} ready"
            if proposals
            else "No documentation proposals are ready"
        )
        pending = f"{coverage_unverified} candidate{' needs' if coverage_unverified == 1 else 's need'} verification"
        return (
            "completed_with_warnings",
            f"{ready}; {pending}.",
        )

    if not state.issues and not state.pull_requests:
        return (
            "no_activity",
            "No relevant issues or merged pull requests were found.",
        )

    if not state.clusters:
        return (
            "no_recommendations",
            "Repository activity was found, but it did not produce a documentation recommendation.",
        )

    actionable_clusters = [
        cluster for cluster in state.clusters if cluster.is_documentation_proposal
    ]
    if not actionable_clusters:
        return (
            "no_recommendations",
            "The identified activity is already documented or has documentation "
            "in progress. No changes are recommended.",
        )

    count = len(actionable_clusters)
    noun = "recommendation is" if count == 1 else "recommendations are"
    return "recommendations_found", f"{count} documentation {noun} ready."
