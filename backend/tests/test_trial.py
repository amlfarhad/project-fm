from argparse import Namespace

from project_fm.trial import run_trial
from tests.test_api import write_synthetic_match_video


def test_trial_cli_report_passes_for_synthetic_match_video(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    video = tmp_path / "synthetic-match.mp4"
    write_synthetic_match_video(video, frames=10, fps=5.0)

    report = run_trial(
        Namespace(
            match_id="trial",
            path=str(video),
            source_type="file",
            stream_url=None,
            duration_ms=1000,
            sample_every_ms=500,
            fps_hint=5.0,
            min_states=2,
            min_observed_players=6,
            min_calibration_confidence=0.6,
            min_processing_fps=1.0,
            min_identity_coverage=0.0,
            min_observed_identity_coverage=0.0,
        )
    )

    assert report["passed"] is True
    assert report["trial_status"] in {"pass", "pass_with_warnings"}
    assert isinstance(report["quality_warnings"], list)
    assert report["summary"]["processor_backend"] == "opencv"
    assert report["summary"]["observed_players"] >= 6


def test_trial_cli_report_fails_when_observed_threshold_is_too_high(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    video = tmp_path / "synthetic-match.mp4"
    write_synthetic_match_video(video, frames=10, fps=5.0)

    report = run_trial(
        Namespace(
            match_id="trial",
            path=str(video),
            source_type="file",
            stream_url=None,
            duration_ms=1000,
            sample_every_ms=500,
            fps_hint=5.0,
            min_states=2,
            min_observed_players=22,
            min_calibration_confidence=0.6,
            min_processing_fps=1.0,
            min_identity_coverage=0.0,
            min_observed_identity_coverage=0.0,
        )
    )

    assert report["passed"] is False
    assert report["trial_status"] == "fail"
    assert "observed_players<22" in report["failures"]


def test_trial_cli_report_enforces_calibration_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    video = tmp_path / "synthetic-match.mp4"
    write_synthetic_match_video(video, frames=10, fps=5.0)

    report = run_trial(
        Namespace(
            match_id="trial",
            path=str(video),
            source_type="file",
            stream_url=None,
            duration_ms=1000,
            sample_every_ms=500,
            fps_hint=5.0,
            min_states=2,
            min_observed_players=6,
            min_calibration_confidence=0.99,
            min_processing_fps=1.0,
            min_identity_coverage=0.0,
            min_observed_identity_coverage=0.0,
        )
    )

    assert report["passed"] is False
    assert "calibration_confidence<0.99" in report["failures"]
