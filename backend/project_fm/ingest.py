from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

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
    ) -> Iterator[FrameMetadata]:
        if duration_ms < 0:
            raise ValueError("duration_ms must be greater than or equal to zero")
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
