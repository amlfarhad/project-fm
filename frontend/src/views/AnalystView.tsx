import { Gauge, RefreshCw, ScanLine, ShieldAlert } from "lucide-react";
import { Pitch } from "../components/Pitch";
import type { TacticalState } from "../types";

interface AnalystViewProps {
  state: TacticalState;
  onRefresh: () => void;
}

export function AnalystView({ state, onRefresh }: AnalystViewProps) {
  const lowConfidence = state.players.filter((player) => player.confidence < 0.7);
  const observed = state.players.filter((player) => player.observed).length;
  const estimated = state.players.length - observed;

  return (
    <main className="analyst-shell">
      <section className="analyst-header">
        <div>
          <p className="eyebrow">Operator Console</p>
          <h1>Live Reconstruction Control</h1>
        </div>
        <div className="analyst-actions">
          <span className="health-chip">
            <Gauge size={16} /> {(state.system_confidence * 100).toFixed(0)}% confidence
          </span>
          <button className="icon-button" onClick={onRefresh} aria-label="Refresh state">
            <RefreshCw size={18} />
          </button>
        </div>
      </section>
      <section className="analyst-grid">
        <div className="panel panel-pitch">
          <div className="panel-heading">
            <h2>Pitch State</h2>
            <span>{state.phase.replace("_", " ")}</span>
          </div>
          <Pitch state={state} compact />
        </div>
        <div className="panel panel-system">
          <h2>System</h2>
          <dl className="metric-list">
            <div>
              <dt>Match</dt>
              <dd>{state.match_id}</dd>
            </div>
            <div>
              <dt>Frame</dt>
              <dd>{state.frame_id}</dd>
            </div>
            <div>
              <dt>Calibration</dt>
              <dd>{state.pitch_calibration.status}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{(state.system_confidence * 100).toFixed(0)}%</dd>
            </div>
          </dl>
        </div>
        <div className="panel panel-kpis">
          <div>
            <ScanLine size={18} />
            <span>Observed</span>
            <strong>{observed}</strong>
          </div>
          <div>
            <ShieldAlert size={18} />
            <span>Estimated</span>
            <strong>{estimated}</strong>
          </div>
        </div>
        <div className="panel panel-table">
          <div className="panel-heading">
            <h2>Low Confidence Tracks</h2>
            <span>{lowConfidence.length} flagged</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Track</th>
                <th>Team</th>
                <th>Role</th>
                <th>Conf.</th>
              </tr>
            </thead>
            <tbody>
              {lowConfidence.map((player) => (
                <tr key={player.track_id}>
                  <td>{player.track_id}</td>
                  <td>{player.team}</td>
                  <td>{player.role_hint}</td>
                  <td>{(player.confidence * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
