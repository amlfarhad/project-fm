import { Activity } from "lucide-react";
import { Pitch } from "../components/Pitch";
import type { TacticalState } from "../types";

interface ManagerViewProps {
  state: TacticalState;
}

export function ManagerView({ state }: ManagerViewProps) {
  const observed = state.players.filter((player) => player.observed).length;

  return (
    <main className="manager-shell">
      <header className="manager-topbar">
        <div>
          <p className="eyebrow">Project FM</p>
          <h1>Live Tactical Map</h1>
        </div>
        <div className="status-pill" aria-label="System confidence">
          <Activity size={18} />
          {(state.system_confidence * 100).toFixed(0)}%
        </div>
      </header>
      <Pitch state={state} />
      <footer className="manager-footer">
        <span>{state.phase.replace("_", " ")}</span>
        <span>{observed}/22 observed</span>
        <span>{(state.timestamp_ms / 1000).toFixed(1)}s</span>
      </footer>
    </main>
  );
}
