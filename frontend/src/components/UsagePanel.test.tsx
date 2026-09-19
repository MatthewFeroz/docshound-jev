import { fireEvent, render, screen } from "@testing-library/react";
import { UsagePanel } from "./UsagePanel";
import { OperationInspector } from "./OperationInspector";

it("explores token metrics and shows the selected call's reported cost", () => {
  render(
    <UsagePanel
      usage={{
        call_count: 1,
        pending_calls: 0,
        failed_calls: 0,
        calls_with_usage: 1,
        calls_without_full_usage: 0,
        unpriced_calls: 0,
        input_tokens: 100,
        output_tokens: 20,
        total_tokens: 120,
        cached_input_tokens: 10,
        reasoning_tokens: 5,
        estimated_cost_usd: null,
        cost_usd: 0.002,
        reported_cost_calls: 1,
        groups: [],
        calls: [
          {
            call_id: "call-1",
            started_at: "2026-09-11T00:00:00Z",
            provider: "merge",
            model: "gpt-5.6-luna",
            operation: "coverage",
            request_status: "succeeded",
            input_tokens: 100,
            output_tokens: 20,
            total_tokens: 120,
            cached_input_tokens: 10,
            reasoning_tokens: 5,
            reported_cost_usd: 0.002,
            estimated_cost_usd: null,
            cost_source: "provider_reported",
            duration_ms: 1200,
          },
        ],
      }}
    />,
  );
  expect(screen.getByText("Provider-reported cost")).toBeInTheDocument();
  expect(
    screen.queryByLabelText("Tokens by model call"),
  ).not.toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: /120\s*Reported tokens/ }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Output" }));
  fireEvent.click(screen.getByRole("button", { name: /Call 1:.*20 tokens/ }));
  expect(screen.getByRole("status")).toHaveTextContent("100 input");
  expect(screen.getByRole("status")).toHaveTextContent("$0.002000");
  expect(screen.getByRole("status")).toHaveTextContent("1.2 s");
});

it("filters operations by query and failure status", () => {
  render(
    <OperationInspector
      events={[
        {
          type: "span_completed",
          span_id: "ok",
          label: "Read docs",
          status: "success",
          stage: "search_docs",
        },
        {
          type: "span_completed",
          span_id: "bad",
          label: "Embed passages",
          status: "error",
          error: "Timed out",
          stage: "search_docs",
        },
      ]}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Errors 1" }));
  expect(screen.queryByText("Read docs")).not.toBeInTheDocument();
  expect(screen.getByText("Embed passages")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Search operations"), {
    target: { value: "nothing" },
  });
  expect(screen.getByText("No matching operations.")).toBeInTheDocument();
});

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
