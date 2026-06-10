from pathlib import Path

from project_fm.domain import CalibrationState, TacticalState
from project_fm.persistence import MatchStateStore


def test_store_appends_and_reads_tactical_states(tmp_path: Path):
    store = MatchStateStore(root=tmp_path)
    state = TacticalState(
        match_id="match-1",
        timestamp_ms=0,
        frame_id="frame-0",
        phase="unknown",
        ball=None,
        players=[],
        pitch_calibration=CalibrationState(status="lost", confidence=0.0, source="test"),
        system_confidence=0.1,
    )

    store.append_state(state)
    loaded = list(store.iter_states("match-1"))

    assert len(loaded) == 1
    assert loaded[0].frame_id == "frame-0"


def test_store_creates_match_directory(tmp_path: Path):
    store = MatchStateStore(root=tmp_path)

    path = store.match_dir("match-2")

    assert path == tmp_path / "match-2"
    assert path.exists()
