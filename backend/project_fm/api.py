from __future__ import annotations

import time
import uuid
import base64
import binascii
import csv
from io import StringIO
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from project_fm.config import get_settings
from project_fm.domain import FrameMetadata, RoleHint, SourceProvenance, TacticalState, Team
from project_fm.ingest import FileVideoSource, OpenCVStreamSource, SourceUnavailableError
from project_fm.persistence import InvalidMatchId, MatchStateStore
from project_fm.pipeline import BaselineProcessor, VideoFrameProcessor

SourceMode = Literal["file", "stream_url"]
MAX_LIVE_IMAGE_DATA_CHARS = 6_000_000
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_ID = "commons-galatasaray-2008"
SAMPLE_VIDEO_PATH = PROJECT_ROOT / "frontend" / "public" / "samples" / "galatasaray-steau-2008-12s.mp4"
SAMPLE_ARTIFACT_PATH = PROJECT_ROOT / "frontend" / "public" / "samples" / "galatasaray-steau-2008-12s.states.json"
SAMPLE_VIDEO_URL = "/samples/galatasaray-steau-2008-12s.mp4"
SAMPLE_ARTIFACT_URL = "/samples/galatasaray-steau-2008-12s.states.json"
SAMPLE_SOURCE_REFERENCE = "https://commons.wikimedia.org/wiki/File:Galatasaray-Steau_Bükreş-1.ogv"
SAMPLE_LICENSE_URL = "https://creativecommons.org/public-domain/mark/1.0/"


class ProcessFileRequest(BaseModel):
    path: str | None = None
    source_type: SourceMode = "file"
    stream_url: str | None = None
    duration_ms: int | None = Field(default=None, gt=0)
    sample_every_ms: int = Field(default=1000, gt=0)
    fps_hint: float | None = Field(default=None, gt=0)
    replace_existing: bool = True
    use_cache: bool = True
    allow_baseline_fallback: bool = False


class ProcessSampleRequest(BaseModel):
    sample_id: str = SAMPLE_ID
    duration_ms: int | None = Field(default=12_000, gt=0)
    sample_every_ms: int = Field(default=1000, gt=0)
    fps_hint: float | None = Field(default=None, gt=0)
    replace_existing: bool = True
    use_cache: bool = True


class ProcessFileResponse(BaseModel):
    match_id: str
    source_id: str
    states_written: int
    replaced_states: int
    first_timestamp_ms: int | None
    latest_timestamp_ms: int | None
    processing_elapsed_ms: int
    processing_fps: float | None
    realtime_factor: float | None
    cache_hit: bool = False
    processor_backend: str
    probe: "SourceProbeResponse"
    provenance: SourceProvenance


class ProcessJobResponse(BaseModel):
    job_id: str
    match_id: str
    status: str
    progress: float = Field(ge=0, le=1)
    frames_processed: int
    total_frames: int | None
    started_at_ms: int
    updated_at_ms: int
    completed_at_ms: int | None
    error: str | None
    result: ProcessFileResponse | None


class SourceProbeRequest(BaseModel):
    path: str | None = None
    source_type: SourceMode = "file"
    stream_url: str | None = None
    fps_hint: float | None = Field(default=None, gt=0)


class SourceProbeResponse(BaseModel):
    source_id: str
    path: str
    width: int | None
    height: int | None
    fps: float | None
    duration_ms: int | None
    frame_count: int | None
    backend: str
    warnings: list[str]


class TrackCorrectionRequest(BaseModel):
    team: Team
    shirt_number: int | None = Field(default=None, ge=1, le=99)
    player_name: str | None = Field(default=None, min_length=1, max_length=120)
    role_hint: RoleHint


class LiveFrameRequest(BaseModel):
    image_data: str = Field(min_length=1, max_length=MAX_LIVE_IMAGE_DATA_CHARS)
    timestamp_ms: int = Field(ge=0)
    width: int = Field(gt=0, le=3840)
    height: int = Field(gt=0, le=2160)
    source_label: str = Field(default="browser-capture", min_length=1, max_length=80)
    fps_hint: float | None = Field(default=None, gt=0)


class LiveFrameResponse(BaseModel):
    match_id: str
    source_id: str
    state: TacticalState
    states_written: int
    processing_elapsed_ms: int
    processor_backend: str


class TrackCorrectionResponse(BaseModel):
    track_id: str
    team: Team
    shirt_number: int | None
    player_name: str | None = None
    role_hint: RoleHint
    corrected_at_ms: int


class MatchSummary(BaseModel):
    match_id: str
    states: int
    latest_timestamp_ms: int | None
    latest_frame_id: str | None
    system_confidence: float | None
    calibration_status: str | None
    calibration_confidence: float | None
    calibration_source: str | None
    observed_players: int | None
    estimated_players: int | None
    shirt_numbered_players: int | None
    observed_shirt_numbered_players: int | None
    named_players: int | None
    identity_coverage: float | None
    observed_identity_coverage: float | None
    quality_warnings: list[str]
    source_id: str | None
    processed_at_ms: int | None
    sample_every_ms: int | None
    replace_existing: bool | None
    processing_elapsed_ms: int | None
    processing_fps: float | None
    realtime_factor: float | None
    corrections: int
    processor_backend: str | None
    provenance: SourceProvenance | None = None


class SampleSourceResponse(BaseModel):
    id: str
    label: str
    description: str
    source_kind: str
    video_url: str
    artifact_url: str
    local_path: str
    duration_ms: int
    width: int
    height: int
    fps: float
    license: str
    license_url: str
    source_reference: str
    attribution: str
    default_sample_every_ms: int
    processing_note: str


app = FastAPI(title="Project FM API")
executor = ThreadPoolExecutor(max_workers=2)
jobs_lock = Lock()
jobs: dict[str, ProcessJobResponse] = {}
live_processors_lock = Lock()
live_processors: dict[str, VideoFrameProcessor] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(InvalidMatchId)
async def invalid_match_id_handler(_request: Request, exc: InvalidMatchId):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/samples")
def list_samples() -> list[SampleSourceResponse]:
    return [sample_descriptor()] if SAMPLE_VIDEO_PATH.is_file() else []


@app.post("/api/matches/{match_id}/process-sample-job")
def start_process_sample_job(match_id: str, request: ProcessSampleRequest) -> ProcessJobResponse:
    if request.sample_id != SAMPLE_ID or not SAMPLE_VIDEO_PATH.is_file():
        raise HTTPException(status_code=404, detail=f"Sample source not found: {request.sample_id}")
    file_request = ProcessFileRequest(
        path=str(SAMPLE_VIDEO_PATH),
        source_type="file",
        duration_ms=request.duration_ms,
        sample_every_ms=request.sample_every_ms,
        fps_hint=request.fps_hint,
        replace_existing=request.replace_existing,
        use_cache=request.use_cache,
    )
    return start_process_file_job(match_id=match_id, request=file_request)


@app.middleware("http")
async def require_api_token(request: Request, call_next):
    token = get_settings().api_token
    if token and request.url.path != "/api/health":
        supplied = request.headers.get("x-project-fm-token")
        if supplied != token:
            return JSONResponse(status_code=401, content={"detail": "Invalid Project FM API token"})
    return await call_next(request)


def get_store() -> MatchStateStore:
    return MatchStateStore(get_settings().data_root)


def sample_descriptor() -> SampleSourceResponse:
    return SampleSourceResponse(
        id=SAMPLE_ID,
        label="Galatasaray–Steaua match clip / 2008",
        description="A bounded public-domain match clip used to exercise the real OpenCV reconstruction path.",
        source_kind="real_video",
        video_url=SAMPLE_VIDEO_URL,
        artifact_url=SAMPLE_ARTIFACT_URL,
        local_path="repository-owned sample asset",
        duration_ms=12_000,
        width=640,
        height=480,
        fps=30.0,
        license="Public domain",
        license_url=SAMPLE_LICENSE_URL,
        source_reference=SAMPLE_SOURCE_REFERENCE,
        attribution="Original uploader Qwl; source clip released into the public domain.",
        default_sample_every_ms=1000,
        processing_note="Hosted demo serves the artifact produced by the OpenCV pipeline; local runs reprocess the clip.",
    )


def sample_provenance(execution_mode: str, processor_backend: str | None = None) -> SourceProvenance:
    descriptor = sample_descriptor()
    return SourceProvenance(
        source_kind="real_video",
        execution_mode=execution_mode,  # type: ignore[arg-type]
        input_label=descriptor.label,
        source_reference=descriptor.source_reference,
        video_url=descriptor.video_url,
        license=descriptor.license,
        license_url=descriptor.license_url,
        attribution=descriptor.attribution,
        pipeline_commit="34c4397",
        processor_backend=processor_backend,
        stages=["input video", "sampled frames", "player detection", "short-track association", "2D pitch state", "analyst review"],
        limitations=[
            "Players outside the camera view are inferred and remain visually distinct from observed detections.",
            "The CPU-safe OpenCV detector is a baseline; shirt-number recognition is not reliable on every frame.",
            "The hosted demo is bounded and precomputed; it is not live footage processing.",
        ],
    )


def provenance_for_request(
    request: ProcessFileRequest,
    source: FileVideoSource | OpenCVStreamSource,
    processor_backend: str,
) -> SourceProvenance:
    if request.allow_baseline_fallback:
        return SourceProvenance(
            source_kind="synthetic_replay",
            execution_mode="synthetic_fallback",
            input_label="Deterministic fallback replay",
            source_reference=None,
            pipeline_commit="34c4397",
            processor_backend=processor_backend,
            stages=["synthetic state generator", "2D pitch state"],
            limitations=["No decodable footage was processed; do not treat these positions as footage evidence."],
        )
    if isinstance(source, FileVideoSource) and source.path.resolve() == SAMPLE_VIDEO_PATH.resolve():
        return sample_provenance("local_pipeline", processor_backend)
    if request.source_type == "stream_url":
        return SourceProvenance(
            source_kind="stream_url",
            execution_mode="local_pipeline",
            input_label="Accessible stream source",
            source_reference=source_locator(request),
            pipeline_commit="34c4397",
            processor_backend=processor_backend,
            stages=["stream input", "sampled frames", "player detection", "short-track association", "2D pitch state", "analyst review"],
            limitations=["Stream availability, camera cuts, and access permissions can interrupt reconstruction."],
        )
    return SourceProvenance(
        source_kind="real_video",
        execution_mode="local_pipeline",
        input_label=Path(source_locator(request)).name or "Local video file",
        source_reference=None,
        pipeline_commit="34c4397",
        processor_backend=processor_backend,
        stages=["input video", "sampled frames", "player detection", "short-track association", "2D pitch state", "analyst review"],
        limitations=["Players outside the camera view are inferred; model quality depends on camera angle and frame quality."],
    )


def live_processor_for(match_id: str) -> VideoFrameProcessor:
    with live_processors_lock:
        processor = live_processors.get(match_id)
        if processor is None:
            processor = VideoFrameProcessor(match_id=match_id)
            live_processors[match_id] = processor
        return processor


def reset_live_processor(match_id: str) -> None:
    with live_processors_lock:
        live_processors.pop(match_id, None)


def summarize_match(store: MatchStateStore, match_id: str) -> MatchSummary:
    latest = corrected_state(store, match_id, store.latest_state(match_id))
    manifest = store.read_manifest(match_id) or {}
    provenance: SourceProvenance | None = None
    raw_provenance = manifest.get("provenance")
    if isinstance(raw_provenance, dict):
        try:
            provenance = SourceProvenance.model_validate(raw_provenance)
        except ValueError:
            provenance = None
    observed_players = sum(1 for player in latest.players if player.observed) if latest else None
    estimated_players = len(latest.players) - observed_players if latest and observed_players is not None else None
    shirt_numbered_players = sum(1 for player in latest.players if player.shirt_number is not None) if latest else None
    observed_shirt_numbered_players = (
        sum(1 for player in latest.players if player.observed and player.shirt_number is not None) if latest else None
    )
    named_players = sum(1 for player in latest.players if player.player_name) if latest else None
    identity_coverage = (
        round(((shirt_numbered_players or 0) + (named_players or 0)) / (len(latest.players) * 2), 3)
        if latest and latest.players
        else None
    )
    observed_identity_coverage = (
        round((observed_shirt_numbered_players or 0) / observed_players, 3)
        if observed_players
        else None
    )
    quality_warnings: list[str] = []
    if latest and observed_players is not None and observed_players < 10:
        quality_warnings.append("low_observed_player_count")
    if latest and latest.pitch_calibration.confidence < 0.6:
        quality_warnings.append("weak_pitch_calibration")
    if identity_coverage is not None and identity_coverage < 0.35:
        quality_warnings.append("low_identity_coverage")
    if observed_identity_coverage is not None and observed_identity_coverage < 0.35:
        quality_warnings.append("low_observed_shirt_number_coverage")
    return MatchSummary(
        match_id=match_id,
        states=store.state_count(match_id),
        latest_timestamp_ms=latest.timestamp_ms if latest else None,
        latest_frame_id=latest.frame_id if latest else None,
        system_confidence=latest.system_confidence if latest else None,
        calibration_status=latest.pitch_calibration.status if latest else None,
        calibration_confidence=latest.pitch_calibration.confidence if latest else None,
        calibration_source=latest.pitch_calibration.source if latest else None,
        observed_players=observed_players,
        estimated_players=estimated_players,
        shirt_numbered_players=shirt_numbered_players,
        observed_shirt_numbered_players=observed_shirt_numbered_players,
        named_players=named_players,
        identity_coverage=identity_coverage,
        observed_identity_coverage=observed_identity_coverage,
        quality_warnings=quality_warnings,
        source_id=manifest.get("source_id") if isinstance(manifest.get("source_id"), str) else None,
        processed_at_ms=manifest.get("processed_at_ms") if isinstance(manifest.get("processed_at_ms"), int) else None,
        sample_every_ms=manifest.get("sample_every_ms") if isinstance(manifest.get("sample_every_ms"), int) else None,
        replace_existing=(
            manifest.get("replace_existing") if isinstance(manifest.get("replace_existing"), bool) else None
        ),
        processing_elapsed_ms=(
            manifest.get("processing_elapsed_ms") if isinstance(manifest.get("processing_elapsed_ms"), int) else None
        ),
        processing_fps=(
            manifest.get("processing_fps")
            if isinstance(manifest.get("processing_fps"), int | float)
            else None
        ),
        realtime_factor=(
            manifest.get("realtime_factor")
            if isinstance(manifest.get("realtime_factor"), int | float)
            else None
        ),
        corrections=len(store.read_corrections(match_id)),
        processor_backend=(
            manifest.get("processor_backend") if isinstance(manifest.get("processor_backend"), str) else None
        ),
        provenance=provenance,
    )


@app.get("/api/matches")
def list_matches() -> list[MatchSummary]:
    store = get_store()
    return [summarize_match(store, match_id) for match_id in store.list_match_ids()]


@app.get("/api/matches/{match_id}/summary")
def match_summary(match_id: str) -> MatchSummary:
    return summarize_match(get_store(), match_id)


@app.get("/api/matches/{match_id}/states")
def match_states(match_id: str, limit: int = 600) -> list[TacticalState]:
    capped_limit = max(1, min(limit, 5000))
    store = get_store()
    states = list(store.iter_states(match_id))
    return corrected_states(store, match_id, states[-capped_limit:])


def stored_states_or_404(match_id: str) -> list[TacticalState]:
    store = get_store()
    states = list(store.iter_states(match_id))
    if not states:
        raise HTTPException(status_code=404, detail=f"No stored tactical states for match: {match_id}")
    return corrected_states(store, match_id, states)


def corrected_state(
    store: MatchStateStore,
    match_id: str,
    state: TacticalState | None,
    corrections: dict[str, dict[str, object]] | None = None,
) -> TacticalState | None:
    if state is None:
        return None
    active_corrections = corrections if corrections is not None else store.read_corrections(match_id)
    if not active_corrections:
        return state

    corrected_players = []
    for player in state.players:
        correction = active_corrections.get(player.track_id)
        if not correction:
            corrected_players.append(player)
            continue
        corrected_players.append(
            player.model_copy(
                update={
                    "team": correction["team"],
                    "shirt_number": correction.get("shirt_number"),
                    "player_name": correction.get("player_name"),
                    "role_hint": correction["role_hint"],
                    "confidence": max(player.confidence, 0.92),
                    "position_status": "corrected",
                },
            )
        )
    return state.model_copy(update={"players": corrected_players})


def corrected_states(
    store: MatchStateStore,
    match_id: str,
    states: list[TacticalState],
) -> list[TacticalState]:
    corrections = store.read_corrections(match_id)
    return [
        state
        for state in (corrected_state(store, match_id, state, corrections=corrections) for state in states)
        if state is not None
    ]


def track_exists_in_match(store: MatchStateStore, match_id: str, track_id: str) -> bool:
    for state in store.iter_states(match_id):
        if any(player.track_id == track_id for player in state.players):
            return True
    return False


@app.get("/api/matches/{match_id}/track-corrections")
def list_track_corrections(match_id: str) -> list[TrackCorrectionResponse]:
    corrections = get_store().read_corrections(match_id)
    return [
        TrackCorrectionResponse(track_id=track_id, **correction)
        for track_id, correction in sorted(corrections.items())
    ]


@app.patch("/api/matches/{match_id}/tracks/{track_id}/correction")
def upsert_track_correction(
    match_id: str,
    track_id: str,
    request: TrackCorrectionRequest,
) -> TrackCorrectionResponse:
    store = get_store()
    if not track_exists_in_match(store, match_id, track_id):
        raise HTTPException(status_code=404, detail=f"Track not found for match: {track_id}")
    correction = {
        "team": request.team,
        "shirt_number": request.shirt_number,
        "player_name": request.player_name,
        "role_hint": request.role_hint,
        "corrected_at_ms": int(time.time() * 1000),
    }
    stored = store.upsert_correction(match_id, track_id, correction)
    return TrackCorrectionResponse(track_id=track_id, **stored)


@app.delete("/api/matches/{match_id}/tracks/{track_id}/correction")
def delete_track_correction(match_id: str, track_id: str) -> dict[str, bool | str]:
    deleted = get_store().delete_correction(match_id, track_id)
    return {"match_id": match_id, "track_id": track_id, "deleted": deleted}


@app.get("/api/matches/{match_id}/export.jsonl")
def export_match_jsonl(match_id: str) -> Response:
    states = stored_states_or_404(match_id)
    body = "".join(f"{state.model_dump_json()}\n" for state in states)
    return Response(
        content=body,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{match_id}-tactical-states.jsonl"'},
    )


@app.get("/api/matches/{match_id}/export.csv")
def export_match_csv(match_id: str) -> Response:
    states = stored_states_or_404(match_id)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "match_id",
            "timestamp_ms",
            "frame_id",
            "phase",
            "track_id",
            "team",
            "shirt_number",
            "role_hint",
            "player_name",
            "pitch_x",
            "pitch_y",
            "observed",
            "confidence",
            "last_observed_ms",
            "ball_x",
            "ball_y",
            "ball_confidence",
            "calibration_status",
            "calibration_confidence",
            "system_confidence",
        ]
    )
    for state in states:
        ball_x = state.ball.pitch_x if state.ball else ""
        ball_y = state.ball.pitch_y if state.ball else ""
        ball_confidence = state.ball.confidence if state.ball else ""
        for player in state.players:
            writer.writerow(
                [
                    state.match_id,
                    state.timestamp_ms,
                    state.frame_id,
                    state.phase,
                    player.track_id,
                    player.team,
                    player.shirt_number or "",
                    player.role_hint,
                    csv_safe_cell(player.player_name or ""),
                    player.pitch_x,
                    player.pitch_y,
                    str(player.observed).lower(),
                    player.confidence,
                    player.last_observed_ms,
                    ball_x,
                    ball_y,
                    ball_confidence,
                    state.pitch_calibration.status,
                    state.pitch_calibration.confidence,
                    state.system_confidence,
                ]
            )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{match_id}-tactical-states.csv"'},
    )


@app.get("/api/matches/{match_id}/latest-state")
def latest_state(match_id: str) -> TacticalState:
    store = get_store()
    latest = store.latest_state(match_id)
    if latest:
        return corrected_state(store, match_id, latest) or latest
    raise HTTPException(status_code=404, detail=f"No stored tactical states for match: {match_id}")


def csv_safe_cell(value: str) -> str:
    return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value


@app.delete("/api/matches/{match_id}")
def delete_match(match_id: str) -> dict[str, bool | str]:
    reset_live_processor(match_id)
    deleted = get_store().delete_match(match_id)
    return {"match_id": match_id, "deleted": deleted}


def safe_source_label(label: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_", "."} else "-" for character in label)[:80]


def decode_live_frame(image_data: str):
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except ImportError as exc:
        raise HTTPException(status_code=422, detail="OpenCV is required for live browser capture.") from exc

    encoded = image_data.split(",", 1)[1] if "," in image_data[:64] else image_data
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="image_data must be a valid base64 image.") from exc

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=422, detail="image_data could not be decoded as an image.")
    return image


@app.post("/api/matches/{match_id}/live-frame")
def ingest_live_frame(match_id: str, request: LiveFrameRequest) -> LiveFrameResponse:
    started_at = time.perf_counter()
    image = decode_live_frame(request.image_data)
    image_height, image_width = image.shape[:2]
    source_id = f"{match_id}:screen:{safe_source_label(request.source_label)}"
    metadata = FrameMetadata(
        frame_id=f"screen-{request.timestamp_ms}",
        source_id=source_id,
        source_type="screen_capture",
        timestamp_ms=request.timestamp_ms,
        wall_clock_ms=int(time.time() * 1000),
        width=image_width or request.width,
        height=image_height or request.height,
        fps_hint=request.fps_hint,
        ingest_latency_ms=0,
    )
    processor = live_processor_for(match_id)
    state = processor.state_for_sample(SimpleNamespace(metadata=metadata, image=image))
    store = get_store()
    store.append_state(state)
    processing_elapsed_ms = max(1, int((time.perf_counter() - started_at) * 1000))
    states_written = store.state_count(match_id)
    provenance = SourceProvenance(
        source_kind="browser_capture",
        execution_mode="live_capture",
        input_label=request.source_label,
        pipeline_commit="34c4397",
        processor_backend="opencv-live",
        stages=["browser capture", "sampled frame", "player detection", "short-track association", "2D pitch state", "analyst review"],
        limitations=["The browser capture depends on the operator's permission and the source's accessible pixels."],
    )
    store.write_manifest(
        match_id,
        {
            "source_id": source_id,
            "path": request.source_label,
            "source_type": "screen_capture",
            "states_written": states_written,
            "replaced_states": 0,
            "first_timestamp_ms": state.timestamp_ms if states_written == 1 else None,
            "latest_timestamp_ms": state.timestamp_ms,
            "duration_ms": None,
            "sample_every_ms": None,
            "fps_hint": request.fps_hint,
            "replace_existing": False,
            "use_cache": False,
            "processed_at_ms": int(time.time() * 1000),
            "probe_backend": "browser-canvas",
            "processor_backend": "opencv-live",
            "processing_elapsed_ms": processing_elapsed_ms,
            "processing_fps": round(1000 / processing_elapsed_ms, 3),
            "realtime_factor": None,
            "provenance": provenance.model_dump(),
        },
    )
    return LiveFrameResponse(
        match_id=match_id,
        source_id=source_id,
        state=state,
        states_written=states_written,
        processing_elapsed_ms=processing_elapsed_ms,
        processor_backend="opencv-live",
    )


def source_locator(request: ProcessFileRequest | SourceProbeRequest) -> str:
    if request.source_type == "stream_url":
        if not request.stream_url:
            raise HTTPException(status_code=422, detail="stream_url is required for stream ingest")
        return request.stream_url
    if not request.path:
        raise HTTPException(status_code=422, detail="path is required for file ingest")
    return request.path


def build_video_source(
    match_id: str,
    request: ProcessFileRequest | SourceProbeRequest,
) -> FileVideoSource | OpenCVStreamSource:
    locator = source_locator(request)
    try:
        if request.source_type == "stream_url":
            return OpenCVStreamSource(url=locator, match_id=match_id, fps_hint=request.fps_hint)
        return FileVideoSource(path=Path(locator).expanduser(), match_id=match_id, fps_hint=request.fps_hint)
    except SourceUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/matches/{match_id}/probe-file")
def probe_file(match_id: str, request: SourceProbeRequest) -> SourceProbeResponse:
    source = build_video_source(match_id=match_id, request=request)
    probe = source.probe()
    return SourceProbeResponse(
        source_id=probe.source_id,
        path=probe.path,
        width=probe.width,
        height=probe.height,
        fps=probe.fps,
        duration_ms=probe.duration_ms,
        frame_count=probe.frame_count,
        backend=probe.backend,
        warnings=list(probe.warnings),
    )


def probe_response(source: FileVideoSource | OpenCVStreamSource) -> SourceProbeResponse:
    probe = source.probe()
    return SourceProbeResponse(
        source_id=probe.source_id,
        path=probe.path,
        width=probe.width,
        height=probe.height,
        fps=probe.fps,
        duration_ms=probe.duration_ms,
        frame_count=probe.frame_count,
        backend=probe.backend,
        warnings=list(probe.warnings),
    )


def estimate_total_frames(source: FileVideoSource | OpenCVStreamSource, request: ProcessFileRequest) -> int | None:
    probe = source.probe()
    duration_ms = request.duration_ms if request.duration_ms is not None else probe.duration_ms
    if duration_ms is None:
        return None
    return int(duration_ms / request.sample_every_ms) + 1


def request_cache_signature(source: FileVideoSource | OpenCVStreamSource, request: ProcessFileRequest) -> dict[str, object]:
    return {
        "source_type": request.source_type,
        "locator": source_locator(request),
        "duration_ms": request.duration_ms,
        "sample_every_ms": request.sample_every_ms,
        "fps_hint": request.fps_hint,
        "allow_baseline_fallback": request.allow_baseline_fallback,
    }


def manifest_matches_request(manifest: dict[str, object], signature: dict[str, object]) -> bool:
    cached_signature = manifest.get("request_signature")
    if isinstance(cached_signature, dict):
        return cached_signature == signature
    return all(manifest.get(key) == value for key, value in signature.items())


def run_process_file(
    match_id: str,
    request: ProcessFileRequest,
    job_id: str | None = None,
) -> ProcessFileResponse:
    store = get_store()
    processing_started_at = time.perf_counter()
    source = build_video_source(match_id=match_id, request=request)
    probe = source.probe()
    signature = request_cache_signature(source, request)
    existing_count = store.state_count(match_id)
    manifest = store.read_manifest(match_id) or {}
    if request.use_cache and request.replace_existing and existing_count > 0 and manifest_matches_request(manifest, signature):
        cached_provenance = None
        if isinstance(manifest.get("provenance"), dict):
            try:
                cached_provenance = SourceProvenance.model_validate(manifest["provenance"])
            except ValueError:
                cached_provenance = None
        cached_provenance = cached_provenance or provenance_for_request(
            request,
            source,
            manifest.get("processor_backend") if isinstance(manifest.get("processor_backend"), str) else "cache",
        )
        return ProcessFileResponse(
            match_id=match_id,
            source_id=source.source_id,
            states_written=existing_count,
            replaced_states=0,
            first_timestamp_ms=(
                manifest.get("first_timestamp_ms") if isinstance(manifest.get("first_timestamp_ms"), int) else None
            ),
            latest_timestamp_ms=(
                manifest.get("latest_timestamp_ms") if isinstance(manifest.get("latest_timestamp_ms"), int) else None
            ),
            processing_elapsed_ms=1,
            processing_fps=(
                manifest.get("processing_fps")
                if isinstance(manifest.get("processing_fps"), int | float)
                else None
            ),
            realtime_factor=(
                manifest.get("realtime_factor")
                if isinstance(manifest.get("realtime_factor"), int | float)
                else None
            ),
            cache_hit=True,
            processor_backend=(
                manifest.get("processor_backend") if isinstance(manifest.get("processor_backend"), str) else "cache"
            ),
            provenance=cached_provenance,
            probe=SourceProbeResponse(
                source_id=probe.source_id,
                path=probe.path,
                width=probe.width,
                height=probe.height,
                fps=probe.fps,
                duration_ms=probe.duration_ms,
                frame_count=probe.frame_count,
                backend=probe.backend,
                warnings=list(probe.warnings),
            ),
        )
    baseline_processor = BaselineProcessor(match_id=match_id)
    cv_processor = VideoFrameProcessor(match_id=match_id)
    first_timestamp_ms: int | None = None
    latest_timestamp_ms: int | None = None
    states: list[TacticalState] = []
    total_frames = estimate_total_frames(source, request)
    processor_backend = "opencv"
    frame_sampling_error: SourceUnavailableError | None = None
    try:
        frame_samples = source.iter_sampled_frames(
            duration_ms=request.duration_ms,
            sample_every_ms=request.sample_every_ms,
        )
        for sample in frame_samples:
            state = cv_processor.state_for_sample(sample)
            states.append(state)
            first_timestamp_ms = sample.metadata.timestamp_ms if first_timestamp_ms is None else first_timestamp_ms
            latest_timestamp_ms = sample.metadata.timestamp_ms
            if job_id:
                update_job(
                    job_id,
                    status="running",
                    frames_processed=len(states),
                    total_frames=total_frames,
                    progress=(min(len(states) / total_frames, 1.0) if total_frames else 0.0),
                )
    except SourceUnavailableError as exc:
        frame_sampling_error = exc

    if not states and not request.allow_baseline_fallback:
        detail = "No decodable video frames were read from this source."
        if frame_sampling_error is not None:
            detail = str(frame_sampling_error)
        raise HTTPException(status_code=422, detail=detail)

    if not states:
        processor_backend = "baseline-fallback"
        for frame in source.iter_sampled_metadata(
            duration_ms=request.duration_ms,
            sample_every_ms=request.sample_every_ms,
        ):
            state = baseline_processor.state_for_metadata(frame)
            states.append(state)
            first_timestamp_ms = frame.timestamp_ms if first_timestamp_ms is None else first_timestamp_ms
            latest_timestamp_ms = frame.timestamp_ms
            if job_id:
                update_job(
                    job_id,
                    status="running",
                    frames_processed=len(states),
                    total_frames=total_frames,
                    progress=(min(len(states) / total_frames, 1.0) if total_frames else 0.0),
                )

    if request.replace_existing:
        store.replace_states(match_id, states)
        store.prune_corrections(
            match_id,
            {player.track_id for state in states for player in state.players},
        )
        replaced_states = existing_count
    else:
        for state in states:
            store.append_state(state)
        replaced_states = 0

    processing_elapsed_ms = max(1, int((time.perf_counter() - processing_started_at) * 1000))
    processing_seconds = processing_elapsed_ms / 1000
    processing_fps = round(len(states) / processing_seconds, 3) if processing_seconds > 0 else None
    match_seconds = (latest_timestamp_ms / 1000) if latest_timestamp_ms else None
    realtime_factor = (
        round(match_seconds / processing_seconds, 3)
        if match_seconds is not None and processing_seconds > 0
        else None
    )
    provenance = provenance_for_request(request, source, processor_backend)

    store.write_manifest(
        match_id,
        {
            "source_id": source.source_id,
            "path": source_locator(request),
            "source_type": request.source_type,
            "states_written": len(states),
            "replaced_states": replaced_states,
            "first_timestamp_ms": first_timestamp_ms,
            "latest_timestamp_ms": latest_timestamp_ms,
            "duration_ms": request.duration_ms,
            "sample_every_ms": request.sample_every_ms,
            "fps_hint": request.fps_hint,
            "replace_existing": request.replace_existing,
            "use_cache": request.use_cache,
            "request_signature": signature,
            "processed_at_ms": int(time.time() * 1000),
            "probe_backend": probe.backend,
            "processor_backend": processor_backend,
            "processing_elapsed_ms": processing_elapsed_ms,
            "processing_fps": processing_fps,
            "realtime_factor": realtime_factor,
            "provenance": provenance.model_dump(),
        },
    )

    return ProcessFileResponse(
        match_id=match_id,
        source_id=source.source_id,
        states_written=len(states),
        replaced_states=replaced_states,
        first_timestamp_ms=first_timestamp_ms,
        latest_timestamp_ms=latest_timestamp_ms,
        processing_elapsed_ms=processing_elapsed_ms,
        processing_fps=processing_fps,
        realtime_factor=realtime_factor,
        cache_hit=False,
        processor_backend=processor_backend,
        provenance=provenance,
        probe=SourceProbeResponse(
            source_id=probe.source_id,
            path=probe.path,
            width=probe.width,
            height=probe.height,
            fps=probe.fps,
            duration_ms=probe.duration_ms,
            frame_count=probe.frame_count,
            backend=probe.backend,
            warnings=list(probe.warnings),
        ),
    )


def update_job(job_id: str, **changes: object) -> None:
    with jobs_lock:
        current = jobs[job_id]
        payload = current.model_dump()
        payload.update(changes)
        payload["updated_at_ms"] = int(time.time() * 1000)
        jobs[job_id] = ProcessJobResponse.model_validate(payload)


def execute_job(job_id: str, match_id: str, request: ProcessFileRequest) -> None:
    update_job(job_id, status="running", progress=0.0)
    try:
        result = run_process_file(match_id=match_id, request=request, job_id=job_id)
    except Exception as exc:  # pragma: no cover - guarded by API-level tests through bad path
        update_job(
            job_id,
            status="failed",
            error=str(exc),
            completed_at_ms=int(time.time() * 1000),
        )
        return
    update_job(
        job_id,
        status="succeeded",
        progress=1.0,
        frames_processed=result.states_written,
        total_frames=result.states_written,
        completed_at_ms=int(time.time() * 1000),
        result=result,
    )


@app.post("/api/matches/{match_id}/process-file")
def process_file(match_id: str, request: ProcessFileRequest) -> ProcessFileResponse:
    return run_process_file(match_id=match_id, request=request)


@app.post("/api/matches/{match_id}/process-file-job")
def start_process_file_job(match_id: str, request: ProcessFileRequest) -> ProcessJobResponse:
    source = build_video_source(match_id=match_id, request=request)
    total_frames = estimate_total_frames(source, request)
    job_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    job = ProcessJobResponse(
        job_id=job_id,
        match_id=match_id,
        status="queued",
        progress=0.0,
        frames_processed=0,
        total_frames=total_frames,
        started_at_ms=now,
        updated_at_ms=now,
        completed_at_ms=None,
        error=None,
        result=None,
    )
    with jobs_lock:
        jobs[job_id] = job
    executor.submit(execute_job, job_id, match_id, request)
    return job


@app.get("/api/process-jobs/{job_id}")
def get_process_job(job_id: str) -> ProcessJobResponse:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Process job not found: {job_id}")
    return job
