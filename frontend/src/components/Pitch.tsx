import type { TacticalState, Team } from "../types";

interface PitchProps {
  state: TacticalState;
  compact?: boolean;
}

function teamClass(team: Team): string {
  if (team === "home") return "player player-home";
  if (team === "away") return "player player-away";
  if (team === "referee") return "player player-referee";
  return "player player-unknown";
}

function positionStatus(player: TacticalState["players"][number]): string {
  return player.position_status ?? (player.observed ? "observed" : "inferred");
}

export function Pitch({ state, compact = false }: PitchProps) {
  return (
    <div className={compact ? "pitch-wrap pitch-wrap-compact" : "pitch-wrap"}>
      <svg viewBox="0 0 105 68" role="img" aria-label="Live reconstructed tactical pitch">
        <rect className="pitch-grass" x="0" y="0" width="105" height="68" rx="0" />
        <rect className="pitch-line" x="2" y="2" width="101" height="64" />
        <line className="pitch-line" x1="52.5" y1="2" x2="52.5" y2="66" />
        <circle className="pitch-line" cx="52.5" cy="34" r="9.15" />
        <circle className="pitch-dot" cx="52.5" cy="34" r="0.45" />
        <rect className="pitch-line" x="2" y="16.5" width="16.5" height="35" />
        <rect className="pitch-line" x="86.5" y="16.5" width="16.5" height="35" />
        <rect className="pitch-line" x="2" y="25" width="5.5" height="18" />
        <rect className="pitch-line" x="97.5" y="25" width="5.5" height="18" />
        {state.ball && (
          <circle className="ball" cx={state.ball.pitch_x} cy={state.ball.pitch_y} r="1.2" />
        )}
        {state.players.map((player) => (
          <g
            key={player.track_id}
            className={`player-state player-state-${positionStatus(player)}`}
            aria-label={`${player.track_id}: ${positionStatus(player)} position`}
          >
            <circle
              className={teamClass(player.team)}
              cx={player.pitch_x}
              cy={player.pitch_y}
              r={compact ? 1.45 : 1.75}
            />
            {!compact && (
              <text className="player-label" x={player.pitch_x} y={player.pitch_y + 0.55}>
                {player.shirt_number ?? ""}
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}
