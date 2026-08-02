from types import SimpleNamespace

import pytest

from project_fm.domain import FrameMetadata
from project_fm.pipeline import BaselineProcessor, VideoFrameProcessor


def synthetic_pitch_frame(home_shift: int = 0, away_shift: int = 0, shirt_numbers: bool = False):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    image = np.zeros((540, 960, 3), dtype=np.uint8)
    image[:, :] = (35, 115, 45)
    cv2.rectangle(image, (70, 55), (890, 485), (48, 130, 58), thickness=-1)
    cv2.rectangle(image, (70, 55), (890, 485), (225, 225, 225), thickness=3)
    players = [
        (210 + home_shift, 160, (35, 35, 210), 7),
        (310 + home_shift, 280, (35, 35, 210), 8),
        (420 + home_shift, 360, (35, 35, 210), 9),
        (650 + away_shift, 170, (230, 230, 230), 4),
        (730 + away_shift, 310, (230, 230, 230), 5),
        (790 + away_shift, 410, (230, 230, 230), 6),
    ]
    for x, y, color, number in players:
        radius = 18 if shirt_numbers else 11
        cv2.circle(image, (x, y), radius, color, thickness=-1)
        if shirt_numbers:
            label = str(number)
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.55
            thickness = 2
            (text_w, text_h), _ = cv2.getTextSize(label, font, scale, thickness)
            ink = (20, 20, 20) if color == (230, 230, 230) else (245, 245, 245)
            cv2.putText(
                image,
                label,
                (x - text_w // 2, y + text_h // 2),
                font,
                scale,
                ink,
                thickness,
                cv2.LINE_AA,
            )
    return image


def test_baseline_processor_emits_twenty_two_players():
    processor = BaselineProcessor(match_id="match-1")

    state = processor.state_for_frame(frame_id="frame-0", timestamp_ms=0)

    assert state.match_id == "match-1"
    assert len(state.players) == 22
    assert state.players[0].team == "home"
    assert state.players[-1].team == "away"


def test_baseline_processor_marks_rest_defense_as_estimated():
    processor = BaselineProcessor(match_id="match-1")

    state = processor.state_for_frame(frame_id="frame-50", timestamp_ms=2000)
    estimated = [player for player in state.players if not player.observed]

    assert estimated
    assert all(player.confidence < 0.8 for player in estimated)


def test_baseline_processor_processes_frame_metadata():
    processor = BaselineProcessor(match_id="match-1")
    frame = {
        "frame_id": "frame-25",
        "timestamp_ms": 1000,
    }

    state = processor.state_for_metadata(frame)

    assert state.frame_id == "frame-25"
    assert state.timestamp_ms == 1000


def test_video_frame_processor_detects_players_from_pixels():
    processor = VideoFrameProcessor(match_id="cv-match")
    sample = SimpleNamespace(
        metadata=FrameMetadata(
            frame_id="frame-0",
            source_id="cv-match:synthetic.mp4",
            source_type="file",
            timestamp_ms=0,
            wall_clock_ms=0,
            width=960,
            height=540,
            fps_hint=25.0,
            ingest_latency_ms=0,
        ),
        image=synthetic_pitch_frame(),
    )

    state = processor.state_for_sample(sample)
    observed = [player for player in state.players if player.observed]

    assert state.pitch_calibration.source == "opencv-green-pitch"
    assert state.pitch_calibration.confidence > 0.6
    assert len(observed) >= 6
    assert len(state.players) == 22
    assert all(player.source_bbox for player in observed)


def test_video_frame_processor_labels_incomplete_detections_as_inferred():
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    image = np.zeros((540, 960, 3), dtype=np.uint8)
    image[:, :] = (35, 115, 45)
    cv2.rectangle(image, (70, 55), (890, 485), (48, 130, 58), thickness=-1)
    processor = VideoFrameProcessor(match_id="incomplete")
    frame = FrameMetadata(
        frame_id="frame-0",
        source_id="incomplete:blank.mp4",
        source_type="file",
        timestamp_ms=0,
        wall_clock_ms=0,
        width=960,
        height=540,
        fps_hint=25.0,
        ingest_latency_ms=0,
    )

    state = processor.state_for_sample(SimpleNamespace(metadata=frame, image=image))

    assert state.players
    assert all(player.position_status == "inferred" for player in state.players)


def test_video_frame_processor_keeps_tracks_stable_across_small_motion():
    processor = VideoFrameProcessor(match_id="cv-match")

    first = processor.state_for_sample(
        SimpleNamespace(
            metadata=FrameMetadata(
                frame_id="frame-0",
                source_id="cv-match:synthetic.mp4",
                source_type="file",
                timestamp_ms=0,
                wall_clock_ms=0,
                width=960,
                height=540,
                fps_hint=25.0,
                ingest_latency_ms=0,
            ),
            image=synthetic_pitch_frame(),
        )
    )
    second = processor.state_for_sample(
        SimpleNamespace(
            metadata=FrameMetadata(
                frame_id="frame-1",
                source_id="cv-match:synthetic.mp4",
                source_type="file",
                timestamp_ms=500,
                wall_clock_ms=500,
                width=960,
                height=540,
                fps_hint=25.0,
                ingest_latency_ms=0,
            ),
            image=synthetic_pitch_frame(home_shift=4, away_shift=-4),
        )
    )

    first_observed = {player.track_id: player.team for player in first.players if player.observed}
    second_observed = {player.track_id: player.team for player in second.players if player.observed}
    shared_tracks = set(first_observed) & set(second_observed)

    assert len(shared_tracks) >= 6
    assert all(first_observed[track_id] == second_observed[track_id] for track_id in shared_tracks)


def test_video_frame_processor_reads_clear_shirt_numbers_from_pixels():
    processor = VideoFrameProcessor(match_id="cv-match")
    state = processor.state_for_sample(
        SimpleNamespace(
            metadata=FrameMetadata(
                frame_id="frame-0",
                source_id="cv-match:synthetic.mp4",
                source_type="file",
                timestamp_ms=0,
                wall_clock_ms=0,
                width=960,
                height=540,
                fps_hint=25.0,
                ingest_latency_ms=0,
            ),
            image=synthetic_pitch_frame(shirt_numbers=True),
        )
    )

    observed_numbers = {player.shirt_number for player in state.players if player.observed and player.shirt_number}

    assert {4, 5, 6, 7, 8, 9}.issubset(observed_numbers)
