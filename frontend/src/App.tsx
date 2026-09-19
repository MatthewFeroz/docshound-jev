import { Navigate, Route, Routes } from "react-router-dom";

import { DocumentPage } from "./pages/DocumentPage";
import { FindingPage } from "./pages/FindingPage";
import { FindingsPage } from "./pages/FindingsPage";
import { UsagePage } from "./pages/UsagePage";
import { HomePage } from "./pages/HomePage";
import { PullRequestPage } from "./pages/PullRequestPage";
import { JevDemoPage } from "./pages/JevDemoPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/jev" element={<JevDemoPage />} />
      <Route path="/showcase" element={<Navigate to="/#overview" replace />} />
      <Route path="/usage" element={<UsagePage />} />
      <Route path="/findings" element={<FindingsPage />} />
      <Route path="/runs/:runId/findings/:index" element={<FindingPage />} />
      <Route path="/documents/:slug" element={<DocumentPage />} />
      <Route
        path="/documents/:slug/pull-request"
        element={<PullRequestPage />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
