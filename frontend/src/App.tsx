import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./layouts/AppLayout";
import { AIAnalysisPage } from "./pages/AIAnalysisPage";
import { MediaPage } from "./pages/MediaPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { RenderPage } from "./pages/RenderPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ScriptPage } from "./pages/ScriptPage";
import { TimelinePage } from "./pages/TimelinePage";

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate replace to="/projects" />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="pipeline" element={<ScriptPage />} />
        <Route path="analysis" element={<AIAnalysisPage />} />
        <Route path="media" element={<MediaPage />} />
        <Route path="render" element={<RenderPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="timeline" element={<TimelinePage />} />
        <Route path="*" element={<Navigate replace to="/projects" />} />
      </Route>
    </Routes>
  );
}
