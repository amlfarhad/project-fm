import { useEffect, useState } from "react";
import { Monitor, Radio } from "lucide-react";
import { fetchLatestState } from "./api";
import { AnalystView } from "./views/AnalystView";
import { ManagerView } from "./views/ManagerView";
import type { TacticalState } from "./types";

type ViewMode = "manager" | "analyst";

export default function App() {
  const [mode, setMode] = useState<ViewMode>("manager");
  const [state, setState] = useState<TacticalState | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadState() {
    try {
      setError(null);
      setState(await fetchLatestState("dev"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  useEffect(() => {
    loadState();
    const timer = window.setInterval(loadState, 2000);
    return () => window.clearInterval(timer);
  }, []);

  if (error) {
    return <div className="center-state">Backend unavailable: {error}</div>;
  }

  if (!state) {
    return <div className="center-state">Loading tactical state</div>;
  }

  return (
    <div className="app-shell">
      <nav className="mode-switch" aria-label="View mode">
        <button className={mode === "manager" ? "active" : ""} onClick={() => setMode("manager")}>
          <Radio size={16} /> Manager
        </button>
        <button className={mode === "analyst" ? "active" : ""} onClick={() => setMode("analyst")}>
          <Monitor size={16} /> Analyst
        </button>
      </nav>
      {mode === "manager" ? (
        <ManagerView state={state} />
      ) : (
        <AnalystView state={state} onRefresh={loadState} />
      )}
    </div>
  );
}
