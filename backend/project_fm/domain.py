from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SourceType = Literal["file", "capture_card", "stream_url", "screen_capture", "camera"]
Team = Literal["home", "away", "referee", "unknown"]
RoleHint = Literal["goalkeeper", "defender", "midfielder", "forward", "referee", "unknown"]
Phase = Literal["in_possession", "out_of_possession", "transition", "set_piece", "unknown"]
CalibrationStatus = Literal["locked", "estimated", "assisted", "lost"]


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
    role_hint: RoleHint
    pitch_x: float = Field(ge=0, le=105)
    pitch_y: float = Field(ge=0, le=68)
    observed: bool
    confidence: float = Field(ge=0, le=1)
    last_observed_ms: int = Field(ge=0)
    source_bbox: list[int] | None = None


class TacticalState(BaseModel):
    match_id: str
    timestamp_ms: int = Field(ge=0)
    frame_id: str
    phase: Phase
    ball: BallState | None
    players: list[PlayerState]
    pitch_calibration: CalibrationState
    system_confidence: float = Field(ge=0, le=1)
