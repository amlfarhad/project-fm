from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


SourceType = Literal["file", "capture_card", "stream_url", "screen_capture", "camera"]
Team = Literal["home", "away", "referee", "unknown"]
RoleHint = Literal["goalkeeper", "defender", "midfielder", "forward", "referee", "unknown"]
Phase = Literal["in_possession", "out_of_possession", "transition", "set_piece", "unknown"]
CalibrationStatus = Literal["locked", "estimated", "assisted", "lost"]
PositionStatus = Literal["observed", "inferred", "corrected", "unavailable"]


class SourceProvenance(BaseModel):
    """Human-readable evidence describing where a tactical state came from."""

    source_kind: Literal["real_video", "synthetic_replay", "browser_capture", "stream_url"]
    execution_mode: Literal["local_pipeline", "precomputed_pipeline", "synthetic_fallback", "live_capture"]
    input_label: str
    source_reference: str | None = None
    video_url: str | None = None
    license: str | None = None
    license_url: str | None = None
    attribution: str | None = None
    pipeline_commit: str | None = None
    processor_backend: str | None = None
    stages: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class FrameMetadata(BaseModel):
    frame_id: str
    source_id: str
    source_type: SourceType
    timestamp_ms: int = Field(ge=0)
    wall_clock_ms: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps_hint: float | None = Field(default=None, gt=0)
    ingest_latency_ms: int | None = Field(default=None, ge=0)


class BallState(BaseModel):
    pitch_x: float = Field(ge=0, le=105)
    pitch_y: float = Field(ge=0, le=68)
    confidence: float = Field(ge=0, le=1)


class CalibrationState(BaseModel):
    status: CalibrationStatus
    confidence: float = Field(ge=0, le=1)
    source: str


class PlayerState(BaseModel):
    track_id: str
    team: Team
    shirt_number: int | None = Field(default=None, ge=1, le=99)
    player_name: str | None = Field(default=None, min_length=1, max_length=120)
    role_hint: RoleHint
    pitch_x: float = Field(ge=0, le=105)
    pitch_y: float = Field(ge=0, le=68)
    observed: bool
    confidence: float = Field(ge=0, le=1)
    last_observed_ms: int = Field(ge=0)
    source_bbox: list[int] | None = None
    position_status: PositionStatus | None = None

    @model_validator(mode="after")
    def infer_position_status(self) -> "PlayerState":
        if self.position_status is None:
            self.position_status = "observed" if self.observed else "inferred"
        return self


class TacticalState(BaseModel):
    match_id: str
    timestamp_ms: int = Field(ge=0)
    frame_id: str
    phase: Phase
    ball: BallState | None
    players: list[PlayerState]
    pitch_calibration: CalibrationState
    system_confidence: float = Field(ge=0, le=1)
