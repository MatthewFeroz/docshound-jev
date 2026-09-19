import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { GapCluster, Run } from "../types";
import { JevDemoPage } from "./JevDemoPage";

const mocks = vi.hoisted(() => ({
  listRuns: vi.fn(),
  getJevDemo: vi.fn(),
  getRun: vi.fn(),
  runJevDemo: vi.fn(),
}));
vi.mock("../api", () => ({ api: mocks }));

const finding: GapCluster = {
  name: "Provider configuration",
  summary: "Unverified migration",
  recurring_question: "How does migration work?",
  issue_numbers: [12451],
  pr_numbers: [],
  issue_refs: ["pingdotgg/t3code#12451"],
  pr_refs: [],
  finding_type: "open_gap",
  severity: "medium",
  confidence: 0.8,
  draft_title: null,
  draft_summary: null,
  draft_markdown: null,
  review_status: "no_change_needed",
  approved_document_slug: null,
  documentation_coverage: null,
  jev_triage: {
    status: "succeeded",
    mode: "shadow",
    answers: {
      readiness: {
        choice: "needs_verification",
        confidence: 0.8,
        probabilities: { needs_verification: 0.9, confirmed: 0.1 },
      },
    },
  },
  jev_assessment: {
    status: "succeeded",
    mode: "shadow",
    recommendation: "verify_implementation",
    answers: {},
    documents: [],
    usage: { cost: 0.0002 },
  },
};
const completed: Run = {
  run_id: "recorded",
  status: "completed",
  outcome: "recommendations_found",
  summary: "Done",
  repo: "pingdotgg/t3code",
  dry_run: true,
  documentation_source: null,
  issues_scraped: 3,
  pull_requests_scraped: 1,
  clusters_found: 1,
  docs_sources: [],
  docs_candidates_inspected: 57,
  documentation_issues_scraped: 0,
  documentation_pull_requests_scraped: 0,
  top_gaps: [finding],
  decisions: [],
  warnings: [],
  errors: [],
  operation_events: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listRuns.mockResolvedValue([completed]);
  mocks.getJevDemo.mockResolvedValue({
    enabled: true,
    selection_note: "Selected cases",
  });
  mocks.getRun.mockResolvedValue(completed);
});

it("shows nondraft findings and Jev's recommendation without calling them approved", async () => {
  render(
    <MemoryRouter initialEntries={["/jev?run=recorded"]}>
      <JevDemoPage />
    </MemoryRouter>,
  );
  expect(
    await screen.findByRole("heading", {
      name: "Verify the implementation first",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("needs verification", { selector: "strong" }),
  ).toBeInTheDocument();
  expect(screen.getByText("$0.00020")).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Inspect the finding →" }),
  ).toHaveAttribute("href", "/runs/recorded/findings/0");
  expect(
    screen.getByText(/No human verdict has been assigned/),
  ).toBeInTheDocument();
});

it("starts the selected live demo and loads the returned run", async () => {
  mocks.runJevDemo.mockResolvedValue({ run_id: "new-live-run" });
  mocks.getRun.mockImplementation(async (id: string) => ({
    ...completed,
    run_id: id,
  }));
  render(
    <MemoryRouter initialEntries={["/jev?run=recorded"]}>
      <JevDemoPage />
    </MemoryRouter>,
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Run live T3Code demo →" }),
    ).toBeEnabled(),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Run live T3Code demo →" }),
  );
  await waitFor(() =>
    expect(mocks.getRun).toHaveBeenCalledWith("new-live-run"),
  );
  expect(mocks.runJevDemo).toHaveBeenCalledTimes(1);
  expect(mocks.runJevDemo).toHaveBeenCalledWith(true);
});

it("shows a held finding as a workflow action rather than an approved draft", async () => {
  mocks.getRun.mockResolvedValue({
    ...completed,
    jev_gate_enabled: true,
    top_gaps: [{ ...finding, jev_draft_hold: "verify_implementation" }],
  });
  render(
    <MemoryRouter initialEntries={["/jev?run=recorded"]}>
      <JevDemoPage />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Draft held")).toBeInTheDocument();
  expect(
    screen.getByText("Draft gate enabled · 1 findings held for verification"),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "Open the draft & source evidence →" }),
  ).not.toBeInTheDocument();
});

it("does not allow starting the demo when Jev is disabled", async () => {
  mocks.getJevDemo.mockResolvedValue({ enabled: false });
  render(
    <MemoryRouter initialEntries={["/jev?run=recorded"]}>
      <JevDemoPage />
    </MemoryRouter>,
  );
  await screen.findByRole("heading", {
    name: "Verify the implementation first",
  });
  expect(
    screen.getByRole("button", { name: "Run live T3Code demo →" }),
  ).toBeDisabled();
});
