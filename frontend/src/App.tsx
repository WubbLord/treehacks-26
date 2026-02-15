import { Navigate, Route, Routes } from "react-router-dom";
import { AgentPage } from "./routes/AgentPage";
import { ManualPage } from "./routes/ManualPage";
import { ReplayPage } from "./routes/ReplayPage";
import { ModeSwitch } from "./components/ModeSwitch";

export function App() {
  return (
    <div className="app-shell">
      <header className="top-bar">
        <h1 className="title">World Viewer</h1>
        <ModeSwitch />
      </header>
      <main className="page-content">
        <Routes>
          <Route path="/" element={<Navigate to="/manual" replace />} />
          <Route path="/manual" element={<ManualPage />} />
          <Route path="/agent" element={<AgentPage />} />
          <Route path="/replay" element={<ReplayPage />} />
        </Routes>
      </main>
    </div>
  );
}

