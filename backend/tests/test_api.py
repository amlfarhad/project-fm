from fastapi.testclient import TestClient

from project_fm.api import app


def test_health_endpoint():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_latest_state_endpoint_returns_tactical_state():
    client = TestClient(app)

    response = client.get("/api/matches/dev/latest-state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["match_id"] == "dev"
    assert len(payload["players"]) == 22


def test_process_match_endpoint_records_states(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_FM_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.post(
        "/api/matches/dev/process-file",
        json={
            "path": __file__,
            "duration_ms": 2000,
            "sample_every_ms": 1000,
            "fps_hint": 25.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["states_written"] == 3
