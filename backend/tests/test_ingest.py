from pathlib import Path

import pytest

from project_fm.ingest import FileVideoSource, SourceUnavailableError


def test_file_source_rejects_missing_path(tmp_path: Path):
    missing = tmp_path / "missing.mp4"

    with pytest.raises(SourceUnavailableError):
        FileVideoSource(path=missing, match_id="match-1")


def test_file_source_builds_metadata_from_existing_file(tmp_path: Path):
    video = tmp_path / "match.mp4"
    video.write_bytes(b"not-a-real-video")

    source = FileVideoSource(path=video, match_id="match-1", fps_hint=25.0)

    assert source.source_id == "match-1:match.mp4"
    assert source.path == video
    assert source.fps_hint == 25.0


def test_file_source_probe_uses_fallback_without_requiring_opencv(tmp_path: Path):
    video = tmp_path / "match.mp4"
    video.write_bytes(b"not-a-real-video")
    source = FileVideoSource(path=video, match_id="match-1", fps_hint=29.97)

    probe = source.probe()

    assert probe.source_id == "match-1:match.mp4"
    assert probe.exists is True
    assert probe.is_file is True
    assert probe.fps == 29.97
    assert probe.backend in {"fallback", "opencv"}


def test_file_source_emits_sampled_frame_metadata(tmp_path: Path):
    video = tmp_path / "match.mp4"
    video.write_bytes(b"not-a-real-video")
    source = FileVideoSource(path=video, match_id="match-1", fps_hint=25.0)

    frames = list(source.iter_sampled_metadata(duration_ms=2000, sample_every_ms=1000))

    assert [frame.frame_id for frame in frames] == ["frame-0", "frame-25", "frame-50"]
    assert [frame.timestamp_ms for frame in frames] == [0, 1000, 2000]


def test_file_source_defaults_to_full_match_when_duration_unknown(tmp_path: Path):
    video = tmp_path / "match.mp4"
    video.write_bytes(b"not-a-real-video")
    source = FileVideoSource(path=video, match_id="match-1", fps_hint=25.0)

    first_frame = next(source.iter_sampled_metadata(sample_every_ms=1000))

    assert first_frame.width == 1920
    assert first_frame.height == 1080
    assert first_frame.fps_hint == 25.0
