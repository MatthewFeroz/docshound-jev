import { render, screen } from "@testing-library/react";
import { UsagePanel } from "./UsagePanel";
import { OperationInspector } from "./OperationInspector";

it("does not present unknown usage or pricing as free", () => {
  render(
    <UsagePanel
      usage={{
        call_count: 1,
        pending_calls: 0,
        failed_calls: 0,
        calls_with_usage: 0,
        calls_without_full_usage: 1,
        unpriced_calls: 1,
        input_tokens: 0,
        output_tokens: 0,
        total_tokens: 0,
        cached_input_tokens: 0,
        reasoning_tokens: 0,
        estimated_cost_usd: null,
        groups: [],
      }}
    />,
  );
  expect(screen.getByText("Unpriced")).toBeInTheDocument();
  expect(
    screen.getByText(/1 with incomplete or unavailable usage/),
  ).toBeInTheDocument();
  expect(screen.queryByText("$0.000000")).not.toBeInTheDocument();
});

it("updates one inspector row across start, progress, and completion", () => {
  const { container } = render(
    <OperationInspector
      events={[
        {
          type: "span_started",
          span_id: "s1",
          label: "Search documentation",
          status: "running",
          stage: "search_docs",
        },
        {
          type: "span_progress",
          span_id: "s1",
          progress_current: 1,
          progress_total: 2,
        },
        {
          type: "span_completed",
          span_id: "s1",
          status: "success",
          output_summary: "2 documents retrieved",
          duration_ms: 12,
        },
      ]}
    />,
  );
  expect(container.querySelectorAll("details")).toHaveLength(1);
  expect(screen.getByText("2 documents retrieved")).toBeInTheDocument();
  expect(screen.getByText("12 ms")).toBeInTheDocument();
});
