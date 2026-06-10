from __future__ import annotations

import math
from typing import Any, cast

from project_fm.domain import BallState, CalibrationState, PlayerState, TacticalState


class BaselineProcessor:
    """Deterministic tactical-state generator for the first product spine.

    This is not the final CV model. It creates real TacticalState records so
    ingest, persistence, APIs, and UI can be built against stable contracts.
    """

    def __init__(self, match_id: str) -> None:
        self.match_id = match_id

    def state_for_frame(self, frame_id: str, timestamp_ms: int) -> TacticalState:
        t = timestamp_ms / 1000
        ball_x = 52.5 + math.sin(t / 8) * 28
        ball_y = 34 + math.cos(t / 5) * 18
        players = self._players(timestamp_ms, ball_x, ball_y)
        observed_count = sum(1 for player in players if player.observed)
        system_confidence = 0.45 + (observed_count / 22) * 0.35

        return TacticalState(
            match_id=self.match_id,
            timestamp_ms=timestamp_ms,
            frame_id=frame_id,
            phase="in_possession",
            ball=BallState(pitch_x=ball_x, pitch_y=ball_y, confidence=0.55),
            players=players,
            pitch_calibration=CalibrationState(
                status="estimated",
                confidence=0.55,
                source="baseline",
            ),
            system_confidence=round(system_confidence, 3),
        )

    def state_for_metadata(self, frame: Any) -> TacticalState:
        if hasattr(frame, "frame_id"):
            return self.state_for_frame(frame_id=frame.frame_id, timestamp_ms=frame.timestamp_ms)
        return self.state_for_frame(frame_id=frame["frame_id"], timestamp_ms=frame["timestamp_ms"])

    def _players(self, timestamp_ms: int, ball_x: float, ball_y: float) -> list[PlayerState]:
        home_shape = [
            (8, 34, "goalkeeper"),
            (22, 12, "defender"),
            (20, 28, "defender"),
            (20, 40, "defender"),
            (22, 56, "defender"),
            (42, 18, "midfielder"),
            (45, 34, "midfielder"),
            (42, 50, "midfielder"),
            (64, 14, "forward"),
            (68, 34, "forward"),
            (64, 54, "forward"),
        ]
        away_shape = [(105 - x, 68 - y, role) for x, y, role in home_shape]
        players: list[PlayerState] = []

        for index, (x, y, role) in enumerate(home_shape, start=1):
            observed = index not in {1, 2, 3}
            players.append(
                self._player(
                    track_id=f"home-{index}",
                    team="home",
                    shirt_number=index,
                    role_hint=role,
                    base_x=x,
                    base_y=y,
                    ball_x=ball_x,
                    ball_y=ball_y,
                    timestamp_ms=timestamp_ms,
                    observed=observed,
                )
            )

        for index, (x, y, role) in enumerate(away_shape, start=1):
            observed = index not in {1, 2}
            players.append(
                self._player(
                    track_id=f"away-{index}",
                    team="away",
                    shirt_number=index,
                    role_hint=role,
                    base_x=x,
                    base_y=y,
                    ball_x=ball_x,
                    ball_y=ball_y,
                    timestamp_ms=timestamp_ms,
                    observed=observed,
                )
            )

        return players

    def _player(
        self,
        track_id: str,
        team: str,
        shirt_number: int,
        role_hint: str,
        base_x: float,
        base_y: float,
        ball_x: float,
        ball_y: float,
        timestamp_ms: int,
        observed: bool,
    ) -> PlayerState:
        pull = 0.07 if role_hint in {"defender", "goalkeeper"} else 0.14
        pitch_x = base_x + (ball_x - base_x) * pull
        pitch_y = base_y + (ball_y - base_y) * pull
        confidence = 0.86 if observed else 0.62

        return PlayerState(
            track_id=track_id,
            team=cast(Any, team),
            shirt_number=shirt_number,
            role_hint=cast(Any, role_hint),
            pitch_x=round(max(0, min(105, pitch_x)), 2),
            pitch_y=round(max(0, min(68, pitch_y)), 2),
            observed=observed,
            confidence=confidence,
            last_observed_ms=timestamp_ms if observed else max(0, timestamp_ms - 4000),
            source_bbox=[0, 0, 0, 0] if observed else None,
        )
