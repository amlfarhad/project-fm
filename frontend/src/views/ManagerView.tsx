import { Activity, CircleDot, Eye, Timer } from "lucide-react";
import { Pitch } from "../components/Pitch";
import type { MatchSummary, TacticalState } from "../types";

interface ManagerViewProps {
  state: TacticalState;
  summary: MatchSummary | null;
}

export function ManagerView({ state, summary }: ManagerViewProps) {
  const observed = state.players.filter((player) => player.observed).length;
  const estimated = state.players.length - observed;
  const confidence = (state.system_confidence * 100).toFixed(0);
  const matchTime = (state.timestamp_ms / 1000).toFixed(1);
  const timelineLabel = summary?.states ? `${summary.states} states` : "live ingest";

  return (
    <main className="manager-shell">
      <header className="manager-topbar">
        <div>
          <p className="eyebrow">Project FM</p>
          <h1>Touchline Tactical Map</h1>
        </div>
        <div className="manager-status-row">
          <div className="status-pill status-live" aria-label="System confidence">
            <Activity size={18} />
            {confidence}%
          </div>
          <div className="status-pill">
            <Eye size={18} />
            {observed}/22
          </div>
        </div>
      </header>
      <section className="manager-stage">
        <aside className="match-rail" aria-label="Live match state">
          <div className="rail-item rail-primary">
            <span>Phase</span>
            <strong>{state.phase.replace("_", " ")}</strong>
          </div>
          <div className="rail-item">
            <span>Observed</span>
            <strong>{observed}</strong>
          </div>
          <div className="rail-item">
            <span>Estimated</span>
            <strong>{estimated}</strong>
          </div>
          <div className="rail-item">
            <span>Calibration</span>
            <strong>{state.pitch_calibration.status}</strong>
          </div>
          <div className="rail-item">
            <span>Timeline</span>
            <strong>{timelineLabel}</strong>
          </div>
        </aside>
        <Pitch state={state} />
      </section>
      <footer className="manager-footer">
        <span>
          <CircleDot size={14} /> full-pitch reconstruction
        </span>
        <span>
          <Timer size={14} /> {matchTime}s feed time
        </span>
        <span>{estimated} inferred rest-defense positions</span>
      </footer>
    </main>
  );
}
