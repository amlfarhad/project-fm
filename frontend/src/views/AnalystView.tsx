import { RefreshCw } from "lucide-react";
import { Pitch } from "../components/Pitch";
import type { TacticalState } from "../types";

interface AnalystViewProps {
  state: TacticalState;
  onRefresh: () => void;
}

export function AnalystView({ state, onRefresh }: AnalystViewProps) {
  const lowConfidence = state.players.filter((player) => player.confidence < 0.7);

  return (
    <main className="analyst-shell">
      <section className="analyst-header">
        <div>
          <p className="eyebrow">Operator Console</p>
          <h1>Match State Diagnostics</h1>
        </div>
        <button className="icon-button" onClick={onRefresh} aria-label="Refresh state">
          <RefreshCw size={18} />
        </button>
      </section>
      <section className="analyst-grid">
        <div className="panel panel-pitch">
          <Pitch state={state} compact />
        </div>
        <div className="panel">
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
        <div className="panel panel-table">
          <h2>Low Confidence Tracks</h2>
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
