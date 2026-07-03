from fastapi.testclient import TestClient
import pytest

from project_fm.api import app


def wait_for_job(client: TestClient, job_id: str):
    for _ in range(50):
        response = client.get(f"/api/process-jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"succeeded", "failed"}:
            return payload
    raise AssertionError("process job did not finish")


def write_synthetic_match_video(path, frames: int = 10, fps: float = 5.0) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (960, 540),
    )
    assert writer.isOpened()
    try:
        for frame_index in range(frames):
            image = np.zeros((540, 960, 3), dtype=np.uint8)
            image[:, :] = (35, 115, 45)
            cv2.rectangle(image, (70, 55), (890, 485), (48, 130, 58), thickness=-1)
            cv2.rectangle(image, (70, 55), (890, 485), (225, 225, 225), thickness=3)
            for x, y, color in [
                (210 + frame_index * 2, 160, (35, 35, 210)),
                (310 + frame_index * 2, 280, (35, 35, 210)),
                (420 + frame_index * 2, 360, (35, 35, 210)),
                (650 - frame_index * 2, 170, (230, 230, 230)),
                (730 - frame_index * 2, 310, (230, 230, 230)),
                (790 - frame_index * 2, 410, (230, 230, 230)),
            ]:
                cv2.circle(image, (x, y), 11, color, thickness=-1)
            writer.write(image)
    finally:
        writer.release()


def synthetic_process_payload(tmp_path, duration_ms: int = 1000, sample_every_ms: int = 500) -> dict[str, object]:
    video = tmp_path / f"synthetic-{duration_ms}-{sample_every_ms}.mp4"
    write_synthetic_match_video(video, frames=12, fps=6.0)
    return {
        "path": str(video),
        "duration_ms": duration_ms,
        "sample_every_ms": sample_every_ms,
        "fps_hint": 6.0,
        "use_cache": False,
    }


def synthetic_frame_data_url() -> str:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    image = np.zeros((540, 960, 3), dtype=np.uint8)
    image[:, :] = (35, 115, 45)
    cv2.rectangle(image, (70, 55), (890, 485), (48, 130, 58), thickness=-1)
    cv2.rectangle(image, (70, 55), (890, 485), (225, 225, 225), thickness=3)
    for x, y, color in [
        (210, 160, (35, 35, 210)),
        (310, 280, (35, 35, 210)),
        (420, 360, (35, 35, 210)),
        (650, 170, (230, 230, 230)),
        (730, 310, (230, 230, 230)),
        (790, 410, (230, 230, 230)),
    ]:
        cv2.circle(image, (x, y), 11, color, thickness=-1)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    import base64

    return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")


def test_health_endpoint():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_token_protects_match_endpoints_but_not_health(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("PROJECT_FM_API_TOKEN", "trial-token")
    client = TestClient(app)

    health = client.get("/api/health")
    blocked = client.get("/api/matches/dev/latest-state")
    allowed = client.get("/api/matches/dev/summary", headers={"x-project-fm-token": "trial-token"})

    assert health.status_code == 200
    assert blocked.status_code == 401
    assert allowed.status_code == 200


def test_latest_state_endpoint_rejects_empty_match(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.get("/api/matches/dev/latest-state")

    assert response.status_code == 404
    assert response.json()["detail"] == "No stored tactical states for match: dev"


def test_latest_state_endpoint_prefers_stored_state(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)
    client.post(
        "/api/matches/stored/process-file",
        json=synthetic_process_payload(tmp_path, duration_ms=1000, sample_every_ms=500),
    )

    response = client.get("/api/matches/stored/latest-state")

    assert response.status_code == 200
    assert response.json()["timestamp_ms"] == 1000


def test_process_match_endpoint_records_states(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.post(
        "/api/matches/dev/process-file",
        json=synthetic_process_payload(tmp_path, duration_ms=1000, sample_every_ms=500),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["states_written"] == 3
    assert payload["replaced_states"] == 0
    assert payload["latest_timestamp_ms"] == 1000
    assert payload["processing_elapsed_ms"] >= 1
    assert payload["processing_fps"] > 0
    assert payload["realtime_factor"] > 0
    assert payload["cache_hit"] is False
    assert payload["probe"]["source_id"].endswith(".mp4")


def test_process_match_endpoint_reuses_matching_cached_timeline(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)
    payload = {
        "path": str(tmp_path / "cache-synthetic.mp4"),
        "duration_ms": 2000,
        "sample_every_ms": 1000,
        "fps_hint": 6.0,
    }
    write_synthetic_match_video(tmp_path / "cache-synthetic.mp4", frames=18, fps=6.0)

    first = client.post("/api/matches/dev/process-file", json=payload)
    second = client.post("/api/matches/dev/process-file", json=payload)
    changed_sample = client.post("/api/matches/dev/process-file", json={**payload, "sample_every_ms": 500})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["cache_hit"] is True
    assert second.json()["states_written"] == 3
    assert second.json()["replaced_states"] == 0
    assert changed_sample.status_code == 200
    assert changed_sample.json()["cache_hit"] is False
    assert changed_sample.json()["states_written"] == 5


def test_process_match_endpoint_uses_opencv_for_real_video_frames(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    video = tmp_path / "synthetic-match.mp4"
    write_synthetic_match_video(video)
    client = TestClient(app)

    response = client.post(
        "/api/matches/cv/process-file",
        json={
            "path": str(video),
            "duration_ms": 1000,
            "sample_every_ms": 500,
            "fps_hint": 5.0,
            "use_cache": False,
        },
    )
    latest_response = client.get("/api/matches/cv/latest-state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["processor_backend"] == "opencv"
    assert payload["states_written"] >= 2
    latest = latest_response.json()
    assert latest["pitch_calibration"]["source"] == "opencv-green-pitch"
    assert len([player for player in latest["players"] if player["observed"]]) >= 6


def test_process_match_endpoint_rejects_non_video_without_explicit_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.post(
        "/api/matches/dev/process-file",
        json={
            "path": __file__,
            "duration_ms": 1000,
            "sample_every_ms": 500,
            "fps_hint": 5.0,
            "use_cache": False,
        },
    )
    summary = client.get("/api/matches/dev/summary")

    assert response.status_code == 422
    assert "video" in response.json()["detail"].lower()
    assert summary.json()["states"] == 0


def test_process_match_endpoint_allows_baseline_fallback_only_when_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.post(
        "/api/matches/dev/process-file",
        json={
            "path": __file__,
            "duration_ms": 1000,
            "sample_every_ms": 500,
            "fps_hint": 5.0,
            "use_cache": False,
            "allow_baseline_fallback": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["processor_backend"] == "baseline-fallback"


def test_process_match_endpoint_accepts_stream_url_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    video = tmp_path / "synthetic-stream.mp4"
    write_synthetic_match_video(video)
    client = TestClient(app)

    response = client.post(
        "/api/matches/live/process-file",
        json={
            "source_type": "stream_url",
            "stream_url": str(video),
            "duration_ms": 1000,
            "sample_every_ms": 500,
            "fps_hint": 5.0,
            "use_cache": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_id"].startswith("live:stream:")
    assert payload["processor_backend"] == "opencv"
    assert payload["states_written"] >= 2


def test_live_frame_endpoint_processes_browser_capture_frame(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    first = client.post(
        "/api/matches/live/live-frame",
        json={
            "image_data": synthetic_frame_data_url(),
            "timestamp_ms": 0,
            "width": 960,
            "height": 540,
            "source_label": "browser-tab",
            "fps_hint": 2,
        },
    )
    second = client.post(
        "/api/matches/live/live-frame",
        json={
            "image_data": synthetic_frame_data_url(),
            "timestamp_ms": 500,
            "width": 960,
            "height": 540,
            "source_label": "browser-tab",
            "fps_hint": 2,
        },
    )
    summary = client.get("/api/matches/live/summary")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["processor_backend"] == "opencv-live"
    assert second.json()["states_written"] == 2
    assert summary.json()["source_id"] == "live:screen:browser-tab"
    assert summary.json()["processor_backend"] == "opencv-live"
    assert len([player for player in second.json()["state"]["players"] if player["observed"]]) >= 6


def test_live_frame_endpoint_rejects_invalid_image_data(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.post(
        "/api/matches/live/live-frame",
        json={
            "image_data": "not-base64",
            "timestamp_ms": 0,
            "width": 960,
            "height": 540,
        },
    )

    assert response.status_code == 422


def test_live_frame_endpoint_rejects_oversized_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.post(
        "/api/matches/live/live-frame",
        json={
            "image_data": "x" * 6_000_001,
            "timestamp_ms": 0,
            "width": 960,
            "height": 540,
        },
    )

    assert response.status_code == 422


def test_process_match_endpoint_rejects_unknown_source_type(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.post(
        "/api/matches/dev/process-file",
        json={
            "source_type": "browser_screen",
            "path": __file__,
            "duration_ms": 1000,
            "sample_every_ms": 500,
            "fps_hint": 5.0,
        },
    )

    assert response.status_code == 422


def test_process_match_job_reports_progress_and_result(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.post(
        "/api/matches/dev/process-file-job",
        json=synthetic_process_payload(tmp_path, duration_ms=1000, sample_every_ms=500),
    )

    assert response.status_code == 200
    queued = response.json()
    assert queued["status"] == "queued"
    assert queued["total_frames"] == 3

    completed = wait_for_job(client, queued["job_id"])
    summary = client.get("/api/matches/dev/summary")

    assert completed["status"] == "succeeded"
    assert completed["progress"] == 1.0
    assert completed["result"]["states_written"] == 3
    assert summary.json()["states"] == 3


def test_process_job_endpoint_rejects_unknown_job():
    client = TestClient(app)

    response = client.get("/api/process-jobs/not-real")

    assert response.status_code == 404


def test_probe_file_endpoint_returns_source_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.post(
        "/api/matches/dev/probe-file",
        json={
            "path": __file__,
            "fps_hint": 30.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_id"] == "dev:test_api.py"
    assert payload["fps"] == 30.0


def test_probe_file_endpoint_rejects_missing_source(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.post(
        "/api/matches/dev/probe-file",
        json={
            "path": str(tmp_path / "missing.mp4"),
        },
    )

    assert response.status_code == 422


def test_match_summary_and_timeline_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)
    client.post(
        "/api/matches/dev/process-file",
        json=synthetic_process_payload(tmp_path, duration_ms=1000, sample_every_ms=500),
    )

    summary_response = client.get("/api/matches/dev/summary")
    states_response = client.get("/api/matches/dev/states?limit=2")
    matches_response = client.get("/api/matches")

    assert summary_response.status_code == 200
    assert summary_response.json()["states"] == 3
    assert summary_response.json()["source_id"].endswith(".mp4")
    assert summary_response.json()["sample_every_ms"] == 500
    assert summary_response.json()["processing_elapsed_ms"] >= 1
    assert summary_response.json()["processing_fps"] > 0
    assert summary_response.json()["realtime_factor"] > 0
    assert summary_response.json()["observed_players"] >= 6
    assert summary_response.json()["estimated_players"] <= 16
    assert summary_response.json()["calibration_confidence"] >= 0.6
    assert summary_response.json()["processor_backend"] == "opencv"
    assert states_response.status_code == 200
    assert [state["timestamp_ms"] for state in states_response.json()] == [500, 1000]
    assert matches_response.status_code == 200
    assert matches_response.json()[0]["match_id"] == "dev"


def test_export_endpoints_return_stored_tactical_data(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)
    client.post(
        "/api/matches/dev/process-file",
        json=synthetic_process_payload(tmp_path, duration_ms=1000, sample_every_ms=500),
    )

    jsonl_response = client.get("/api/matches/dev/export.jsonl")
    csv_response = client.get("/api/matches/dev/export.csv")

    assert jsonl_response.status_code == 200
    assert jsonl_response.headers["content-type"].startswith("application/x-ndjson")
    assert len(jsonl_response.text.strip().splitlines()) == 3
    assert '"match_id":"dev"' in jsonl_response.text
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "match_id,timestamp_ms,frame_id" in csv_response.text
    assert "cv-" in csv_response.text


def test_track_correction_applies_to_latest_timeline_summary_and_export(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)
    client.post(
        "/api/matches/dev/process-file",
        json=synthetic_process_payload(tmp_path, duration_ms=1000, sample_every_ms=500),
    )
    stored_latest = client.get("/api/matches/dev/latest-state").json()
    target_track = next(player["track_id"] for player in stored_latest["players"] if player["observed"])

    correction_response = client.patch(
        f"/api/matches/dev/tracks/{target_track}/correction",
        json={"team": "away", "shirt_number": 44, "player_name": "=Test Midfielder", "role_hint": "midfielder"},
    )
    latest_response = client.get("/api/matches/dev/latest-state")
    states_response = client.get("/api/matches/dev/states")
    summary_response = client.get("/api/matches/dev/summary")
    csv_response = client.get("/api/matches/dev/export.csv")
    corrections_response = client.get("/api/matches/dev/track-corrections")

    assert correction_response.status_code == 200
    assert correction_response.json()["team"] == "away"
    assert correction_response.json()["shirt_number"] == 44
    assert correction_response.json()["player_name"] == "=Test Midfielder"
    corrected_latest = next(
        player for player in latest_response.json()["players"] if player["track_id"] == target_track
    )
    corrected_timeline_state = next(
        player
        for state in states_response.json()
        for player in state["players"]
        if player["track_id"] == target_track
    )
    assert corrected_latest["team"] == "away"
    assert corrected_latest["shirt_number"] == 44
    assert corrected_latest["player_name"] == "=Test Midfielder"
    assert corrected_latest["role_hint"] == "midfielder"
    assert corrected_latest["confidence"] == 0.92
    assert corrected_timeline_state["team"] == "away"
    assert summary_response.json()["corrections"] == 1
    assert f",{target_track},away,44,midfielder,'=Test Midfielder," in csv_response.text
    assert corrections_response.json()[0]["track_id"] == target_track


def test_process_match_replace_prunes_stale_track_corrections(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    video = tmp_path / "synthetic-match.mp4"
    write_synthetic_match_video(video)
    client = TestClient(app)
    baseline_payload = {
        "path": __file__,
        "duration_ms": 1000,
        "sample_every_ms": 1000,
        "fps_hint": 25.0,
        "use_cache": False,
        "allow_baseline_fallback": True,
    }

    client.post("/api/matches/dev/process-file", json=baseline_payload)
    correction_response = client.patch(
        "/api/matches/dev/tracks/home-1/correction",
        json={"team": "away", "shirt_number": 44, "role_hint": "midfielder"},
    )
    replace_response = client.post(
        "/api/matches/dev/process-file",
        json={
            "path": str(video),
            "duration_ms": 1000,
            "sample_every_ms": 500,
            "fps_hint": 5.0,
            "use_cache": False,
        },
    )
    corrections_response = client.get("/api/matches/dev/track-corrections")
    summary_response = client.get("/api/matches/dev/summary")

    assert correction_response.status_code == 200
    assert replace_response.status_code == 200
    assert replace_response.json()["processor_backend"] == "opencv"
    assert corrections_response.json() == []
    assert summary_response.json()["corrections"] == 0


def test_track_correction_rejects_unknown_track(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.patch(
        "/api/matches/dev/tracks/not-real/correction",
        json={"team": "home", "shirt_number": 12, "role_hint": "defender"},
    )

    assert response.status_code == 404


def test_match_id_rejects_unsafe_path_segments(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.get("/api/matches/.hidden/summary")

    assert response.status_code == 422


def test_export_endpoint_rejects_empty_match(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.get("/api/matches/empty/export.csv")

    assert response.status_code == 404


def test_process_match_endpoint_replaces_existing_states_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)
    payload = synthetic_process_payload(tmp_path, duration_ms=2000, sample_every_ms=1000)

    first = client.post("/api/matches/dev/process-file", json=payload)
    second = client.post("/api/matches/dev/process-file", json=payload)
    summary = client.get("/api/matches/dev/summary")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["replaced_states"] == first.json()["states_written"]
    assert summary.json()["states"] == second.json()["states_written"]


def test_process_match_endpoint_can_append_when_requested(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)
    payload = synthetic_process_payload(tmp_path, duration_ms=1000, sample_every_ms=1000)

    client.post("/api/matches/dev/process-file", json=payload)
    response = client.post(
        "/api/matches/dev/process-file",
        json={**payload, "replace_existing": False},
    )
    summary = client.get("/api/matches/dev/summary")

    assert response.status_code == 200
    assert response.json()["replaced_states"] == 0
    assert summary.json()["states"] == 4


def test_delete_match_endpoint_removes_timeline(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)
    client.post(
        "/api/matches/dev/process-file",
        json=synthetic_process_payload(tmp_path, duration_ms=1000, sample_every_ms=500),
    )

    delete_response = client.delete("/api/matches/dev")
    summary_response = client.get("/api/matches/dev/summary")

    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True
    assert summary_response.json()["states"] == 0
