export type Team = "home" | "away" | "referee" | "unknown";
export type RoleHint = "goalkeeper" | "defender" | "midfielder" | "forward" | "referee" | "unknown";

export interface BallState {
  pitch_x: number;
  pitch_y: number;
  confidence: number;
}

export interface PlayerState {
  track_id: string;
  team: Team;
  shirt_number: number | null;
  player_name: string | null;
  role_hint: RoleHint;
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

export interface MatchSummary {
  match_id: string;
  states: number;
  latest_timestamp_ms: number | null;
  latest_frame_id: string | null;
  system_confidence: number | null;
  calibration_status: string | null;
  calibration_confidence: number | null;
  calibration_source: string | null;
  observed_players: number | null;
  estimated_players: number | null;
  shirt_numbered_players: number | null;
  observed_shirt_numbered_players: number | null;
  named_players: number | null;
  identity_coverage: number | null;
  observed_identity_coverage: number | null;
  quality_warnings: string[];
  source_id: string | null;
  processed_at_ms: number | null;
  sample_every_ms: number | null;
  replace_existing: boolean | null;
  processing_elapsed_ms: number | null;
  processing_fps: number | null;
  realtime_factor: number | null;
  corrections: number;
  processor_backend: string | null;
}

export interface ProcessFilePayload {
  path: string | null;
  source_type: "file" | "stream_url";
  stream_url: string | null;
  duration_ms: number | null;
  sample_every_ms: number;
  fps_hint: number | null;
  replace_existing: boolean;
  use_cache: boolean;
}

export interface SourceProbe {
  source_id: string;
  path: string;
  width: number | null;
  height: number | null;
  fps: number | null;
  duration_ms: number | null;
  frame_count: number | null;
  backend: string;
  warnings: string[];
}

export interface ProcessFileResult {
  match_id: string;
  source_id: string;
  states_written: number;
  replaced_states: number;
  first_timestamp_ms: number | null;
  latest_timestamp_ms: number | null;
  processing_elapsed_ms: number;
  processing_fps: number | null;
  realtime_factor: number | null;
  cache_hit: boolean;
  processor_backend: string;
  probe: SourceProbe;
}

export interface LiveFramePayload {
  image_data: string;
  timestamp_ms: number;
  width: number;
  height: number;
  source_label: string;
  fps_hint: number | null;
}

export interface LiveFrameResult {
  match_id: string;
  source_id: string;
  state: TacticalState;
  states_written: number;
  processing_elapsed_ms: number;
  processor_backend: string;
}

export type ProcessJobStatus = "queued" | "running" | "succeeded" | "failed";

export interface ProcessJob {
  job_id: string;
  match_id: string;
  status: ProcessJobStatus;
  progress: number;
  frames_processed: number;
  total_frames: number | null;
  started_at_ms: number;
  updated_at_ms: number;
  completed_at_ms: number | null;
  error: string | null;
  result: ProcessFileResult | null;
}

export interface DeleteMatchResult {
  match_id: string;
  deleted: boolean;
}

export interface TrackCorrectionPayload {
  team: Team;
  shirt_number: number | null;
  player_name: string | null;
  role_hint: RoleHint;
}

export interface TrackCorrection extends TrackCorrectionPayload {
  track_id: string;
  corrected_at_ms: number;
}
