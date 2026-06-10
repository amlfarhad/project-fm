from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from project_fm.config import get_settings
from project_fm.ingest import FileVideoSource
from project_fm.persistence import MatchStateStore
from project_fm.pipeline import BaselineProcessor


class ProcessFileRequest(BaseModel):
    path: str
    duration_ms: int = Field(default=90 * 60 * 1000, gt=0)
    sample_every_ms: int = Field(default=1000, gt=0)
    fps_hint: float | None = Field(default=25.0, gt=0)


app = FastAPI(title="Project FM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/matches/{match_id}/latest-state")
def latest_state(match_id: str):
    processor = BaselineProcessor(match_id=match_id)
    return processor.state_for_frame(frame_id="frame-live", timestamp_ms=12_000)


@app.post("/api/matches/{match_id}/process-file")
def process_file(match_id: str, request: ProcessFileRequest) -> dict[str, int | str]:
    settings = get_settings()
    store = MatchStateStore(settings.data_root)
    source = FileVideoSource(path=Path(request.path), match_id=match_id, fps_hint=request.fps_hint)
    processor = BaselineProcessor(match_id=match_id)
    count = 0
    for frame in source.iter_sampled_metadata(
        duration_ms=request.duration_ms,
        sample_every_ms=request.sample_every_ms,
    ):
        store.append_state(processor.state_for_metadata(frame))
        count += 1
    return {"match_id": match_id, "states_written": count}
