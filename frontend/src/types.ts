export type Team = "home" | "away" | "referee" | "unknown";

export interface BallState {
  pitch_x: number;
  pitch_y: number;
  confidence: number;
}

export interface PlayerState {
  track_id: string;
  team: Team;
  shirt_number: number | null;
  role_hint: string;
  pitch_x: number;
  pitch_y: number;
  observed: boolean;
  confidence: number;
  last_observed_ms: number;
  source_bbox: number[] | null;
}

export interface CalibrationState {
  status: string;
  confidence: number;
  source: string;
}

export interface TacticalState {
  match_id: string;
  timestamp_ms: number;
  frame_id: string;
  phase: string;
  ball: BallState | null;
  players: PlayerState[];
  pitch_calibration: CalibrationState;
  system_confidence: number;
}
