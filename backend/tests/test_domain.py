from project_fm.domain import (
    BallState,
    CalibrationState,
    FrameMetadata,
    PlayerState,
    TacticalState,
)


def test_tactical_state_round_trip():
    state = TacticalState(
        match_id="match-1",
        timestamp_ms=1200,
        frame_id="frame-12",
        phase="in_possession",
        ball=BallState(pitch_x=52.0, pitch_y=34.0, confidence=0.7),
        players=[
            PlayerState(
                track_id="home-4",
                team="home",
                shirt_number=4,
                role_hint="defender",
                pitch_x=20.0,
                pitch_y=40.0,
                observed=True,
                confidence=0.92,
                last_observed_ms=1200,
                source_bbox=[100, 120, 24, 58],
            )
        ],
        pitch_calibration=CalibrationState(
            status="estimated",
            confidence=0.65,
            source="baseline",
        ),
        system_confidence=0.72,
    )

    payload = state.model_dump()
    restored = TacticalState.model_validate(payload)

    assert restored.match_id == "match-1"
    assert restored.players[0].track_id == "home-4"
    assert restored.players[0].source_bbox == [100, 120, 24, 58]
    assert restored.players[0].position_status == "observed"


def test_frame_metadata_records_source_details():
    frame = FrameMetadata(
        frame_id="frame-1",
        source_id="file-a",
        source_type="file",
        timestamp_ms=40,
        wall_clock_ms=1000,
        width=1920,
        height=1080,
        fps_hint=25.0,
        ingest_latency_ms=None,
    )

    assert frame.source_type == "file"
    assert frame.fps_hint == 25.0
