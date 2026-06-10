from project_fm.pipeline import BaselineProcessor


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
