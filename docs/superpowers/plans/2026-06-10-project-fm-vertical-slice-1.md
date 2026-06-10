# Project FM Vertical Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first real Project FM product slice: full-match-file ingest treated as a live stream, tactical state persistence, backend APIs, and manager/analyst web clients fed by real pipeline output.

**Architecture:** Use a Python backend for video pipeline, schemas, persistence, and APIs, plus a React/Vite frontend for manager and analyst views. The first slice uses deterministic baseline detectors and generated/cached tactical state so the full product spine works on a MacBook Air before heavier CV models are added.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, OpenCV optional for video probing/frame reads, pytest, TypeScript, React, Vite, CSS modules/plain CSS, browser-based SVG/Canvas pitch rendering.

---

## Scope

This plan implements a vertical product spine, not the full AI stack. It must process full-match files through live-shaped interfaces and render real pipeline-produced tactical state. Model quality improves in later plans.

In scope:
- Monorepo scaffold.
- Backend config and domain schemas.
- Full-match file ingest abstraction.
- Local JSONL persistence for events and tactical states.
- Baseline frame processor that emits deterministic observed/estimated players.
- Backend API endpoints for health, latest state, and full-match-file processing.
- Manager view: full-pitch 2D tactical map.
- Analyst view: source controls, timeline, diagnostics, and state table.
- Tests and verification.

Out of scope:
- Training custom CV models.
- Perfect broadcast calibration.
- Shirt-number OCR.
- True live screen/capture-card ingest.
- Native iPad app.
- Club outreach list.

## UI Skill Stack

Chosen from the Optimum Mode UI skills index:
- Product/UX shaping: `shape`
- Operational interface craft: `interface-design`
- Grid/layout discipline: `swiss-design`, `layout`
- Noise reduction: `distill`
- Typography: `typeset`
- Responsive adaptation: `adapt`
- Edge states: `harden`
- Accessibility: `fixing-accessibility`
- Framework quality: `react-best-practices`
- Performance: `optimize`
- Final polish: `polish`

Design direction: calm, tactical, touchline-readable, information-dense without dashboard clutter. Manager view is glanceable. Analyst view is denser and exposes uncertainty.

## File Structure

Create:
- `README.md` - project purpose, local setup, first slice commands.
- `.gitignore` - Python, Node, match data, caches, and local env ignores.
- `backend/pyproject.toml` - backend dependencies and pytest config.
- `backend/project_fm/__init__.py` - package marker.
- `backend/project_fm/config.py` - typed runtime paths and settings.
- `backend/project_fm/domain.py` - Frame, PlayerState, TacticalState, and related schemas.
- `backend/project_fm/ingest.py` - full-match file source abstraction.
- `backend/project_fm/persistence.py` - JSONL match-state store.
- `backend/project_fm/pipeline.py` - baseline processor and match processing orchestration.
- `backend/project_fm/api.py` - FastAPI app.
- `backend/tests/test_domain.py` - schema tests.
- `backend/tests/test_ingest.py` - ingest tests using a temporary local source.
- `backend/tests/test_persistence.py` - JSONL store tests.
- `backend/tests/test_pipeline.py` - baseline processor tests.
- `frontend/package.json` - frontend scripts and dependencies.
- `frontend/index.html` - app shell.
- `frontend/tsconfig.json` - TypeScript config.
- `frontend/vite.config.ts` - Vite config and API proxy.
- `frontend/src/main.tsx` - app bootstrap.
- `frontend/src/App.tsx` - routes/view switching.
- `frontend/src/api.ts` - backend client.
- `frontend/src/types.ts` - frontend tactical state types.
- `frontend/src/components/Pitch.tsx` - 2D pitch renderer.
- `frontend/src/views/ManagerView.tsx` - touchline view.
- `frontend/src/views/AnalystView.tsx` - operator view.
- `frontend/src/styles.css` - product visual system.

## Task 1: Repository And Backend Scaffold

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `backend/pyproject.toml`
- Create: `backend/project_fm/__init__.py`

- [ ] **Step 1: Create repository basics**

Create `README.md`:

```markdown
# Project FM

Project FM is a live tactical reconstruction system for football clubs. It ingests match video as a stream, reconstructs a full-pitch 2D tactical state, and serves manager and analyst web views.

## First Slice

The first product slice runs on a MacBook Air with full-match files. It treats files as live streams, stores tactical state output, and renders the state in browser clients.

## Local Development

Backend:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
uvicorn project_fm.api:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Data

Do not commit match videos, model weights, local caches, credentials, or private club/contact data.
```

Create `.gitignore`:

```gitignore
.DS_Store
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
node_modules/
dist/
.env
.env.*
data/
matches/
outputs/
models/
*.mp4
*.mov
*.mkv
*.avi
```

- [ ] **Step 2: Create backend package metadata**

Create `backend/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "project-fm"
version = "0.1.0"
description = "Live tactical reconstruction system for football match video."
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "pydantic>=2.7",
  "uvicorn[standard]>=0.30",
  "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "httpx>=0.27",
]
video = [
  "opencv-python>=4.10",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Create `backend/project_fm/__init__.py`:

```python
"""Project FM backend package."""

__all__ = ["__version__"]

__version__ = "0.1.0"
```

- [ ] **Step 3: Install backend dependencies**

Run:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Expected: install completes without dependency resolution errors.

- [ ] **Step 4: Commit scaffold**

Run:

```bash
git add README.md .gitignore backend/pyproject.toml backend/project_fm/__init__.py
git commit -m "chore: scaffold Project FM backend"
```

Expected: commit succeeds.

## Task 2: Domain Schemas

**Files:**
- Create: `backend/project_fm/domain.py`
- Create: `backend/tests/test_domain.py`

- [ ] **Step 1: Write schema tests**

Create `backend/tests/test_domain.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
. .venv/bin/activate
pytest tests/test_domain.py -v
```

Expected: FAIL because `project_fm.domain` does not exist.

- [ ] **Step 3: Implement schemas**

Create `backend/project_fm/domain.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SourceType = Literal["file", "capture_card", "stream_url", "screen_capture", "camera"]
Team = Literal["home", "away", "referee", "unknown"]
RoleHint = Literal["goalkeeper", "defender", "midfielder", "forward", "referee", "unknown"]
Phase = Literal["in_possession", "out_of_possession", "transition", "set_piece", "unknown"]
CalibrationStatus = Literal["locked", "estimated", "assisted", "lost"]


class FrameMetadata(BaseModel):
    frame_id: str
    source_id: str
    source_type: SourceType
    timestamp_ms: int = Field(ge=0)
    wall_clock_ms: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps_hint: float | None = Field(default=None, gt=0)
    ingest_latency_ms: int | None = Field(default=None, ge=0)


class BallState(BaseModel):
    pitch_x: float = Field(ge=0, le=105)
    pitch_y: float = Field(ge=0, le=68)
    confidence: float = Field(ge=0, le=1)


class CalibrationState(BaseModel):
    status: CalibrationStatus
    confidence: float = Field(ge=0, le=1)
    source: str


class PlayerState(BaseModel):
    track_id: str
    team: Team
    shirt_number: int | None = Field(default=None, ge=1, le=99)
    role_hint: RoleHint
    pitch_x: float = Field(ge=0, le=105)
    pitch_y: float = Field(ge=0, le=68)
    observed: bool
    confidence: float = Field(ge=0, le=1)
    last_observed_ms: int = Field(ge=0)
    source_bbox: list[int] | None = None


class TacticalState(BaseModel):
    match_id: str
    timestamp_ms: int = Field(ge=0)
    frame_id: str
    phase: Phase
    ball: BallState | None
    players: list[PlayerState]
    pitch_calibration: CalibrationState
    system_confidence: float = Field(ge=0, le=1)
```

- [ ] **Step 4: Run schema tests**

Run:

```bash
cd backend
. .venv/bin/activate
pytest tests/test_domain.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit schemas**

Run:

```bash
git add backend/project_fm/domain.py backend/tests/test_domain.py
git commit -m "feat: add tactical state schemas"
```

Expected: commit succeeds.

## Task 3: File Ingest Abstraction

**Files:**
- Create: `backend/project_fm/ingest.py`
- Create: `backend/tests/test_ingest.py`

- [ ] **Step 1: Write ingest tests**

Create `backend/tests/test_ingest.py`:

```python
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


def test_file_source_emits_sampled_frame_metadata(tmp_path: Path):
    video = tmp_path / "match.mp4"
    video.write_bytes(b"not-a-real-video")
    source = FileVideoSource(path=video, match_id="match-1", fps_hint=25.0)

    frames = list(source.iter_sampled_metadata(duration_ms=2000, sample_every_ms=1000))

    assert [frame.frame_id for frame in frames] == ["frame-0", "frame-25", "frame-50"]
    assert [frame.timestamp_ms for frame in frames] == [0, 1000, 2000]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
. .venv/bin/activate
pytest tests/test_ingest.py -v
```

Expected: FAIL because `project_fm.ingest` does not exist.

- [ ] **Step 3: Implement ingest source**

Create `backend/project_fm/ingest.py`:

```python
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from project_fm.domain import FrameMetadata


class SourceUnavailableError(RuntimeError):
    """Raised when a configured video source cannot be opened."""


@dataclass(frozen=True)
class FileVideoSource:
    path: Path
    match_id: str
    fps_hint: float | None = None

    def __post_init__(self) -> None:
        if not self.path.exists():
            raise SourceUnavailableError(f"Video file does not exist: {self.path}")
        if not self.path.is_file():
            raise SourceUnavailableError(f"Video path is not a file: {self.path}")

    @property
    def source_id(self) -> str:
        return f"{self.match_id}:{self.path.name}"

    def iter_sampled_metadata(
        self,
        duration_ms: int = 90 * 60 * 1000,
        sample_every_ms: int = 1000,
        width: int = 1920,
        height: int = 1080,
    ):
        if sample_every_ms <= 0:
            raise ValueError("sample_every_ms must be greater than zero")
        fps = self.fps_hint or 25.0
        wall_clock_ms = int(time.time() * 1000)
        for timestamp_ms in range(0, duration_ms + 1, sample_every_ms):
            frame_number = int((timestamp_ms / 1000) * fps)
            yield FrameMetadata(
                frame_id=f"frame-{frame_number}",
                source_id=self.source_id,
                source_type="file",
                timestamp_ms=timestamp_ms,
                wall_clock_ms=wall_clock_ms,
                width=width,
                height=height,
                fps_hint=fps,
                ingest_latency_ms=0,
            )
```

- [ ] **Step 4: Run ingest tests**

Run:

```bash
cd backend
. .venv/bin/activate
pytest tests/test_ingest.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit ingest abstraction**

Run:

```bash
git add backend/project_fm/ingest.py backend/tests/test_ingest.py
git commit -m "feat: add file video source abstraction"
```

Expected: commit succeeds.

## Task 4: Persistence Store

**Files:**
- Create: `backend/project_fm/persistence.py`
- Create: `backend/tests/test_persistence.py`

- [ ] **Step 1: Write persistence tests**

Create `backend/tests/test_persistence.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
. .venv/bin/activate
pytest tests/test_persistence.py -v
```

Expected: FAIL because `project_fm.persistence` does not exist.

- [ ] **Step 3: Implement JSONL store**

Create `backend/project_fm/persistence.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from project_fm.domain import TacticalState


class MatchStateStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def match_dir(self, match_id: str) -> Path:
        path = self.root / match_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def states_path(self, match_id: str) -> Path:
        return self.match_dir(match_id) / "tactical_states.jsonl"

    def append_state(self, state: TacticalState) -> None:
        path = self.states_path(state.match_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(state.model_dump_json())
            handle.write("\n")

    def iter_states(self, match_id: str) -> Iterator[TacticalState]:
        path = self.states_path(match_id)
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    yield TacticalState.model_validate(json.loads(stripped))
```

- [ ] **Step 4: Run persistence tests**

Run:

```bash
cd backend
. .venv/bin/activate
pytest tests/test_persistence.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit persistence**

Run:

```bash
git add backend/project_fm/persistence.py backend/tests/test_persistence.py
git commit -m "feat: persist tactical state timeline"
```

Expected: commit succeeds.

## Task 5: Baseline Processing Pipeline

**Files:**
- Create: `backend/project_fm/pipeline.py`
- Create: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write pipeline tests**

Create `backend/tests/test_pipeline.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
. .venv/bin/activate
pytest tests/test_pipeline.py -v
```

Expected: FAIL because `project_fm.pipeline` does not exist.

- [ ] **Step 3: Implement baseline processor**

Create `backend/project_fm/pipeline.py`:

```python
from __future__ import annotations

import math

from project_fm.domain import BallState, CalibrationState, PlayerState, TacticalState


class BaselineProcessor:
    """Deterministic tactical-state generator for the first product spine.

    This is not the final CV model. It creates real TacticalState records so
    ingest, persistence, APIs, and UI can be built against stable contracts.
    """

    def __init__(self, match_id: str) -> None:
        self.match_id = match_id

    def state_for_frame(self, frame_id: str, timestamp_ms: int) -> TacticalState:
        t = timestamp_ms / 1000
        ball_x = 52.5 + math.sin(t / 8) * 28
        ball_y = 34 + math.cos(t / 5) * 18
        players = self._players(timestamp_ms, ball_x, ball_y)
        observed_count = sum(1 for player in players if player.observed)
        system_confidence = 0.45 + (observed_count / 22) * 0.35

        return TacticalState(
            match_id=self.match_id,
            timestamp_ms=timestamp_ms,
            frame_id=frame_id,
            phase="in_possession",
            ball=BallState(pitch_x=ball_x, pitch_y=ball_y, confidence=0.55),
            players=players,
            pitch_calibration=CalibrationState(
                status="estimated",
                confidence=0.55,
                source="baseline",
            ),
            system_confidence=round(system_confidence, 3),
        )

    def state_for_metadata(self, frame) -> TacticalState:
        if hasattr(frame, "frame_id"):
            return self.state_for_frame(frame_id=frame.frame_id, timestamp_ms=frame.timestamp_ms)
        return self.state_for_frame(frame_id=frame["frame_id"], timestamp_ms=frame["timestamp_ms"])

    def _players(self, timestamp_ms: int, ball_x: float, ball_y: float) -> list[PlayerState]:
        home_shape = [
            (8, 34, "goalkeeper"),
            (22, 12, "defender"),
            (20, 28, "defender"),
            (20, 40, "defender"),
            (22, 56, "defender"),
            (42, 18, "midfielder"),
            (45, 34, "midfielder"),
            (42, 50, "midfielder"),
            (64, 14, "forward"),
            (68, 34, "forward"),
            (64, 54, "forward"),
        ]
        away_shape = [(105 - x, 68 - y, role) for x, y, role in home_shape]
        players: list[PlayerState] = []

        for index, (x, y, role) in enumerate(home_shape, start=1):
            observed = index not in {1, 2, 3}
            players.append(
                self._player(
                    track_id=f"home-{index}",
                    team="home",
                    shirt_number=index,
                    role_hint=role,
                    base_x=x,
                    base_y=y,
                    ball_x=ball_x,
                    ball_y=ball_y,
                    timestamp_ms=timestamp_ms,
                    observed=observed,
                )
            )

        for index, (x, y, role) in enumerate(away_shape, start=1):
            observed = index not in {1, 2}
            players.append(
                self._player(
                    track_id=f"away-{index}",
                    team="away",
                    shirt_number=index,
                    role_hint=role,
                    base_x=x,
                    base_y=y,
                    ball_x=ball_x,
                    ball_y=ball_y,
                    timestamp_ms=timestamp_ms,
                    observed=observed,
                )
            )

        return players

    def _player(
        self,
        track_id: str,
        team: str,
        shirt_number: int,
        role_hint: str,
        base_x: float,
        base_y: float,
        ball_x: float,
        ball_y: float,
        timestamp_ms: int,
        observed: bool,
    ) -> PlayerState:
        pull = 0.07 if role_hint in {"defender", "goalkeeper"} else 0.14
        pitch_x = base_x + (ball_x - base_x) * pull
        pitch_y = base_y + (ball_y - base_y) * pull
        confidence = 0.86 if observed else 0.62

        return PlayerState(
            track_id=track_id,
            team=team,  # type: ignore[arg-type]
            shirt_number=shirt_number,
            role_hint=role_hint,  # type: ignore[arg-type]
            pitch_x=round(max(0, min(105, pitch_x)), 2),
            pitch_y=round(max(0, min(68, pitch_y)), 2),
            observed=observed,
            confidence=confidence,
            last_observed_ms=timestamp_ms if observed else max(0, timestamp_ms - 4000),
            source_bbox=[0, 0, 0, 0] if observed else None,
        )
```

- [ ] **Step 4: Run pipeline tests**

Run:

```bash
cd backend
. .venv/bin/activate
pytest tests/test_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit baseline processor**

Run:

```bash
git add backend/project_fm/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: add baseline tactical processor"
```

Expected: commit succeeds.

## Task 6: Backend API

**Files:**
- Create: `backend/project_fm/config.py`
- Create: `backend/project_fm/api.py`
- Create: `backend/tests/test_api.py`

- [ ] **Step 1: Write API tests**

Create `backend/tests/test_api.py`:

```python
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


def test_process_match_endpoint_records_states():
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
. .venv/bin/activate
pytest tests/test_api.py -v
```

Expected: FAIL because `project_fm.api` does not exist.

- [ ] **Step 3: Implement config and API**

Create `backend/project_fm/config.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_root: Path


def get_settings() -> Settings:
    root = Path(os.environ.get("PROJECT_FM_DATA_ROOT", "data")).resolve()
    return Settings(data_root=root)
```

Create `backend/project_fm/api.py`:

```python
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
```

- [ ] **Step 4: Run API tests**

Run:

```bash
cd backend
. .venv/bin/activate
pytest tests/test_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit API**

Run:

```bash
git add backend/project_fm/config.py backend/project_fm/api.py backend/tests/test_api.py
git commit -m "feat: expose tactical state api"
```

Expected: commit succeeds.

## Task 7: Frontend Scaffold And Tactical Pitch

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/components/Pitch.tsx`
- Create: `frontend/src/views/ManagerView.tsx`
- Create: `frontend/src/views/AnalystView.tsx`
- Create: `frontend/src/styles.css`

- [ ] **Step 1: Create frontend package**

Create `frontend/package.json`:

```json
{
  "name": "project-fm-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc && vite build",
    "preview": "vite preview --host 127.0.0.1"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0",
    "typescript": "^5.5.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "lucide-react": "^0.468.0"
  },
  "devDependencies": {}
}
```

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Project FM</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": []
}
```

Create `frontend/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000"
    }
  }
});
```

- [ ] **Step 2: Create frontend types and API client**

Create `frontend/src/types.ts`:

```ts
export type Team = "home" | "away" | "referee" | "unknown";

export interface BallState {
  pitch_x: number;
  pitch_y: number;
  confidence: number;
}

export interface PlayerState {
  track_id: string;
  team: Team;
  shirt_number: number | null;
  role_hint: string;
  pitch_x: number;
  pitch_y: number;
  observed: boolean;
  confidence: number;
  last_observed_ms: number;
  source_bbox: number[] | null;
}

export interface CalibrationState {
  status: string;
  confidence: number;
  source: string;
}

export interface TacticalState {
  match_id: string;
  timestamp_ms: number;
  frame_id: string;
  phase: string;
  ball: BallState | null;
  players: PlayerState[];
  pitch_calibration: CalibrationState;
  system_confidence: number;
}
```

Create `frontend/src/api.ts`:

```ts
import type { TacticalState } from "./types";

export async function fetchLatestState(matchId: string): Promise<TacticalState> {
  const response = await fetch(`/api/matches/${matchId}/latest-state`);
  if (!response.ok) {
    throw new Error(`Failed to fetch tactical state: ${response.status}`);
  }
  return response.json();
}
```

- [ ] **Step 3: Create pitch renderer**

Create `frontend/src/components/Pitch.tsx`:

```tsx
import type { TacticalState, Team } from "../types";

interface PitchProps {
  state: TacticalState;
  compact?: boolean;
}

function teamClass(team: Team): string {
  if (team === "home") return "player player-home";
  if (team === "away") return "player player-away";
  if (team === "referee") return "player player-referee";
  return "player player-unknown";
}

export function Pitch({ state, compact = false }: PitchProps) {
  return (
    <div className={compact ? "pitch-wrap pitch-wrap-compact" : "pitch-wrap"}>
      <svg viewBox="0 0 105 68" role="img" aria-label="Live reconstructed tactical pitch">
        <rect className="pitch-grass" x="0" y="0" width="105" height="68" rx="0" />
        <rect className="pitch-line" x="2" y="2" width="101" height="64" />
        <line className="pitch-line" x1="52.5" y1="2" x2="52.5" y2="66" />
        <circle className="pitch-line" cx="52.5" cy="34" r="9.15" />
        <circle className="pitch-dot" cx="52.5" cy="34" r="0.45" />
        <rect className="pitch-line" x="2" y="16.5" width="16.5" height="35" />
        <rect className="pitch-line" x="86.5" y="16.5" width="16.5" height="35" />
        <rect className="pitch-line" x="2" y="25" width="5.5" height="18" />
        <rect className="pitch-line" x="97.5" y="25" width="5.5" height="18" />
        {state.ball && (
          <circle
            className="ball"
            cx={state.ball.pitch_x}
            cy={state.ball.pitch_y}
            r="1.2"
          />
        )}
        {state.players.map((player) => (
          <g key={player.track_id} className={player.observed ? "observed" : "estimated"}>
            <circle
              className={teamClass(player.team)}
              cx={player.pitch_x}
              cy={player.pitch_y}
              r={compact ? 1.45 : 1.75}
            />
            {!compact && (
              <text className="player-label" x={player.pitch_x} y={player.pitch_y + 0.55}>
                {player.shirt_number ?? ""}
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}
```

- [ ] **Step 4: Create views and app shell**

Create `frontend/src/views/ManagerView.tsx`:

```tsx
import { Activity } from "lucide-react";
import { Pitch } from "../components/Pitch";
import type { TacticalState } from "../types";

interface ManagerViewProps {
  state: TacticalState;
}

export function ManagerView({ state }: ManagerViewProps) {
  const observed = state.players.filter((player) => player.observed).length;

  return (
    <main className="manager-shell">
      <header className="manager-topbar">
        <div>
          <p className="eyebrow">Project FM</p>
          <h1>Live Tactical Map</h1>
        </div>
        <div className="status-pill" aria-label="System confidence">
          <Activity size={18} />
          {(state.system_confidence * 100).toFixed(0)}%
        </div>
      </header>
      <Pitch state={state} />
      <footer className="manager-footer">
        <span>{state.phase.replace("_", " ")}</span>
        <span>{observed}/22 observed</span>
        <span>{(state.timestamp_ms / 1000).toFixed(1)}s</span>
      </footer>
    </main>
  );
}
```

Create `frontend/src/views/AnalystView.tsx`:

```tsx
import { RefreshCw } from "lucide-react";
import { Pitch } from "../components/Pitch";
import type { TacticalState } from "../types";

interface AnalystViewProps {
  state: TacticalState;
  onRefresh: () => void;
}

export function AnalystView({ state, onRefresh }: AnalystViewProps) {
  const lowConfidence = state.players.filter((player) => player.confidence < 0.7);

  return (
    <main className="analyst-shell">
      <section className="analyst-header">
        <div>
          <p className="eyebrow">Operator Console</p>
          <h1>Match State Diagnostics</h1>
        </div>
        <button className="icon-button" onClick={onRefresh} aria-label="Refresh state">
          <RefreshCw size={18} />
        </button>
      </section>
      <section className="analyst-grid">
        <div className="panel panel-pitch">
          <Pitch state={state} compact />
        </div>
        <div className="panel">
          <h2>System</h2>
          <dl className="metric-list">
            <div><dt>Match</dt><dd>{state.match_id}</dd></div>
            <div><dt>Frame</dt><dd>{state.frame_id}</dd></div>
            <div><dt>Calibration</dt><dd>{state.pitch_calibration.status}</dd></div>
            <div><dt>Confidence</dt><dd>{(state.system_confidence * 100).toFixed(0)}%</dd></div>
          </dl>
        </div>
        <div className="panel panel-table">
          <h2>Low Confidence Tracks</h2>
          <table>
            <thead>
              <tr>
                <th>Track</th>
                <th>Team</th>
                <th>Role</th>
                <th>Conf.</th>
              </tr>
            </thead>
            <tbody>
              {lowConfidence.map((player) => (
                <tr key={player.track_id}>
                  <td>{player.track_id}</td>
                  <td>{player.team}</td>
                  <td>{player.role_hint}</td>
                  <td>{(player.confidence * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
```

Create `frontend/src/App.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Monitor, Radio } from "lucide-react";
import { fetchLatestState } from "./api";
import { AnalystView } from "./views/AnalystView";
import { ManagerView } from "./views/ManagerView";
import type { TacticalState } from "./types";

type ViewMode = "manager" | "analyst";

export default function App() {
  const [mode, setMode] = useState<ViewMode>("manager");
  const [state, setState] = useState<TacticalState | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadState() {
    try {
      setError(null);
      setState(await fetchLatestState("dev"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  useEffect(() => {
    loadState();
    const timer = window.setInterval(loadState, 2000);
    return () => window.clearInterval(timer);
  }, []);

  if (error) {
    return <div className="center-state">Backend unavailable: {error}</div>;
  }

  if (!state) {
    return <div className="center-state">Loading tactical state</div>;
  }

  return (
    <div className="app-shell">
      <nav className="mode-switch" aria-label="View mode">
        <button className={mode === "manager" ? "active" : ""} onClick={() => setMode("manager")}>
          <Radio size={16} /> Manager
        </button>
        <button className={mode === "analyst" ? "active" : ""} onClick={() => setMode("analyst")}>
          <Monitor size={16} /> Analyst
        </button>
      </nav>
      {mode === "manager" ? <ManagerView state={state} /> : <AnalystView state={state} onRefresh={loadState} />}
    </div>
  );
}
```

Create `frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 5: Create visual system CSS**

Create `frontend/src/styles.css`:

```css
:root {
  color: #eef3ee;
  background: #101411;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background: #101411;
}

button {
  font: inherit;
}

.app-shell {
  min-height: 100vh;
}

.mode-switch {
  position: fixed;
  right: 16px;
  top: 16px;
  z-index: 10;
  display: flex;
  gap: 6px;
  padding: 4px;
  border: 1px solid #314137;
  background: rgba(16, 20, 17, 0.92);
}

.mode-switch button,
.icon-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 0;
  color: #c9d7cd;
  background: transparent;
  padding: 9px 11px;
  cursor: pointer;
}

.mode-switch button.active,
.icon-button:hover {
  color: #ffffff;
  background: #243229;
}

.manager-shell {
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto 1fr auto;
  padding: 28px;
  gap: 18px;
}

.manager-topbar,
.manager-footer,
.analyst-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.eyebrow {
  margin: 0 0 6px;
  color: #8fa395;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0;
}

h1,
h2 {
  margin: 0;
  letter-spacing: 0;
}

h1 {
  font-size: 30px;
  line-height: 1.05;
}

h2 {
  font-size: 16px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #3d5a45;
  background: #17231b;
  color: #d8f7df;
  padding: 10px 12px;
}

.manager-footer {
  color: #c9d7cd;
  font-size: 14px;
  border-top: 1px solid #26332b;
  padding-top: 14px;
}

.pitch-wrap {
  width: 100%;
  height: 100%;
  min-height: 420px;
  display: grid;
  align-items: center;
}

.pitch-wrap svg {
  width: 100%;
  max-height: calc(100vh - 180px);
  aspect-ratio: 105 / 68;
  display: block;
}

.pitch-wrap-compact {
  min-height: 320px;
}

.pitch-wrap-compact svg {
  max-height: 420px;
}

.pitch-grass {
  fill: #1e5f3b;
}

.pitch-line {
  fill: none;
  stroke: rgba(238, 243, 238, 0.78);
  stroke-width: 0.35;
}

.pitch-dot {
  fill: rgba(238, 243, 238, 0.82);
}

.player {
  stroke: #101411;
  stroke-width: 0.45;
}

.player-home {
  fill: #e9f1f2;
}

.player-away {
  fill: #db3e34;
}

.player-referee {
  fill: #f3cc4d;
}

.player-unknown {
  fill: #9ba7a0;
}

.estimated {
  opacity: 0.52;
}

.player-label {
  fill: #101411;
  font-size: 2.15px;
  font-weight: 800;
  text-anchor: middle;
  dominant-baseline: middle;
}

.ball {
  fill: #f4d35e;
  stroke: #101411;
  stroke-width: 0.35;
}

.analyst-shell {
  min-height: 100vh;
  padding: 28px;
}

.analyst-header {
  margin-bottom: 20px;
  padding-right: 190px;
}

.analyst-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(260px, 0.6fr);
  gap: 14px;
}

.panel {
  border: 1px solid #2b3930;
  background: #151c18;
  padding: 16px;
}

.panel-pitch,
.panel-table {
  grid-row: span 2;
}

.metric-list {
  display: grid;
  gap: 12px;
  margin: 14px 0 0;
}

.metric-list div {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

dt {
  color: #8fa395;
}

dd {
  margin: 0;
  color: #eef3ee;
}

table {
  width: 100%;
  margin-top: 12px;
  border-collapse: collapse;
  font-size: 14px;
}

th,
td {
  padding: 10px 8px;
  border-bottom: 1px solid #2b3930;
  text-align: left;
}

th {
  color: #8fa395;
  font-weight: 600;
}

.center-state {
  min-height: 100vh;
  display: grid;
  place-items: center;
  color: #c9d7cd;
}

@media (max-width: 820px) {
  .mode-switch {
    left: 12px;
    right: 12px;
    top: auto;
    bottom: 12px;
    justify-content: center;
  }

  .manager-shell,
  .analyst-shell {
    padding: 18px;
    padding-bottom: 76px;
  }

  .manager-topbar,
  .manager-footer,
  .analyst-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .analyst-header {
    padding-right: 0;
  }

  .analyst-grid {
    grid-template-columns: 1fr;
  }

  .panel-pitch,
  .panel-table {
    grid-row: auto;
  }
}
```

- [ ] **Step 6: Install frontend dependencies**

Run:

```bash
cd frontend
npm install
```

Expected: install completes and creates `package-lock.json`.

- [ ] **Step 7: Build frontend**

Run:

```bash
cd frontend
npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 8: Commit frontend**

Run:

```bash
git add frontend
git commit -m "feat: add tactical web clients"
```

Expected: commit succeeds.

## Task 8: End-To-End Local Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run backend tests**

Run:

```bash
cd backend
. .venv/bin/activate
pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: build passes.

- [ ] **Step 3: Start backend server**

Run:

```bash
cd backend
. .venv/bin/activate
uvicorn project_fm.api:app --host 127.0.0.1 --port 8000
```

Expected: server starts and exposes `http://127.0.0.1:8000/api/health`.

- [ ] **Step 4: Start frontend server**

Run:

```bash
cd frontend
npm run dev
```

Expected: Vite serves `http://127.0.0.1:5173`.

- [ ] **Step 5: Browser QA**

Open `http://127.0.0.1:5173`.

Expected:
- Manager view loads by default.
- Pitch renders with 22 players and a ball.
- System confidence is visible.
- View switch changes to Analyst view.
- Analyst view lists low-confidence tracks.
- No text overlaps at laptop width.
- At tablet width, view switch moves to bottom and pitch remains readable.

- [ ] **Step 6: Update README verification status**

Add this section to `README.md`:

```markdown
## Verification

Current verified slice:
- Backend schema, ingest, persistence, pipeline, and API tests.
- Frontend TypeScript/Vite build.
- Browser QA for manager and analyst views.
```

- [ ] **Step 7: Commit verification docs**

Run:

```bash
git add README.md
git commit -m "docs: document vertical slice verification"
```

Expected: commit succeeds.

## Security And Privacy Check

Before considering this plan complete, run:

```bash
rg -n "sk-|api_key|secret|token|password|/Users/|@|\\.env" .
```

Expected:
- No secrets.
- No private emails.
- Local absolute paths only appear in committed planning/spec files if needed for Codex file references; source code must not contain private local paths.

## Final Verification Gate

Report:
- Backend tests: PASS / FAIL / UNVERIFIABLE.
- Frontend build: PASS / FAIL / UNVERIFIABLE.
- Browser QA: PASS / FAIL / UNVERIFIABLE.
- Security/privacy scan: CLEAN / CONFIRM / BLOCK.
- Remaining product risks.
