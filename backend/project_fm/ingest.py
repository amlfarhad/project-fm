from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from project_fm.domain import FrameMetadata


class SourceUnavailableError(RuntimeError):
    """Raised when a configured video source cannot be opened."""


@dataclass(frozen=True)
class VideoProbe:
    source_id: str
    path: str
    exists: bool
    is_file: bool
    width: int | None
    height: int | None
    fps: float | None
    duration_ms: int | None
    frame_count: int | None
    backend: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class VideoFrameSample:
    metadata: FrameMetadata
    image: Any


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

    def probe(self) -> VideoProbe:
        warnings: list[str] = []
        width: int | None = None
        height: int | None = None
        fps: float | None = self.fps_hint
        duration_ms: int | None = None
        frame_count: int | None = None
        backend = "fallback"

        try:
            import cv2  # type: ignore[import-not-found]
        except ImportError:
            warnings.append("OpenCV is not installed; using configured FPS and fallback dimensions.")
        else:
            capture = cv2.VideoCapture(str(self.path))
            try:
                if capture.isOpened():
                    backend = "opencv"
                    raw_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                    raw_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    raw_fps = float(capture.get(cv2.CAP_PROP_FPS))
                    raw_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

                    width = raw_width if raw_width > 0 else None
                    height = raw_height if raw_height > 0 else None
                    fps = raw_fps if raw_fps > 0 else fps
                    frame_count = raw_frame_count if raw_frame_count > 0 else None
                    if frame_count and fps:
                        duration_ms = int((frame_count / fps) * 1000)
                else:
                    warnings.append("OpenCV could not open this file as video; using fallback metadata.")
            finally:
                capture.release()

        return VideoProbe(
            source_id=self.source_id,
            path=str(self.path),
            exists=self.path.exists(),
            is_file=self.path.is_file(),
            width=width,
            height=height,
            fps=fps,
            duration_ms=duration_ms,
            frame_count=frame_count,
            backend=backend,
            warnings=tuple(warnings),
        )

    def iter_sampled_metadata(
        self,
        duration_ms: int | None = None,
        sample_every_ms: int = 1000,
        width: int | None = None,
        height: int | None = None,
    ) -> Iterator[FrameMetadata]:
        if duration_ms is not None and duration_ms < 0:
            raise ValueError("duration_ms must be greater than or equal to zero")
        if sample_every_ms <= 0:
            raise ValueError("sample_every_ms must be greater than zero")

        probe = self.probe()
        effective_duration_ms = duration_ms if duration_ms is not None else probe.duration_ms
        effective_duration_ms = effective_duration_ms if effective_duration_ms is not None else 90 * 60 * 1000
        fps = probe.fps or 25.0
        frame_width = width or probe.width or 1920
        frame_height = height or probe.height or 1080
        wall_clock_ms = int(time.time() * 1000)
        for timestamp_ms in range(0, effective_duration_ms + 1, sample_every_ms):
            frame_number = int((timestamp_ms / 1000) * fps)
            yield FrameMetadata(
                frame_id=f"frame-{frame_number}",
                source_id=self.source_id,
                source_type="file",
                timestamp_ms=timestamp_ms,
                wall_clock_ms=wall_clock_ms,
                width=frame_width,
                height=frame_height,
                fps_hint=fps,
                ingest_latency_ms=0,
            )

    def iter_sampled_frames(
        self,
        duration_ms: int | None = None,
        sample_every_ms: int = 1000,
    ) -> Iterator[VideoFrameSample]:
        try:
            import cv2  # type: ignore[import-not-found]
        except ImportError as exc:
            raise SourceUnavailableError("OpenCV is required for frame sampling.") from exc

        probe = self.probe()
        fps = probe.fps or 25.0
        effective_duration_ms = duration_ms if duration_ms is not None else probe.duration_ms
        if effective_duration_ms is None:
            effective_duration_ms = 90 * 60 * 1000

        capture = cv2.VideoCapture(str(self.path))
        if not capture.isOpened():
            capture.release()
            raise SourceUnavailableError(f"OpenCV could not open video frames: {self.path}")

        try:
            for metadata in self.iter_sampled_metadata(
                duration_ms=effective_duration_ms,
                sample_every_ms=sample_every_ms,
                width=probe.width,
                height=probe.height,
            ):
                capture.set(cv2.CAP_PROP_POS_MSEC, metadata.timestamp_ms)
                ok, image = capture.read()
                if not ok or image is None:
                    continue
                yield VideoFrameSample(metadata=metadata, image=image)
        finally:
            capture.release()


@dataclass(frozen=True)
class OpenCVStreamSource:
    url: str
    match_id: str
    fps_hint: float | None = None

    @property
    def source_id(self) -> str:
        parsed = urlparse(self.url)
        if parsed.scheme and parsed.netloc:
            label = f"{parsed.scheme}-{parsed.netloc}{parsed.path}".strip("/")
        else:
            label = Path(self.url).name or "stream"
        safe_label = "".join(character if character.isalnum() or character in {"-", "_", "."} else "-" for character in label)
        return f"{self.match_id}:stream:{safe_label[:80]}"

    def probe(self) -> VideoProbe:
        warnings: list[str] = []
        width: int | None = None
        height: int | None = None
        fps: float | None = self.fps_hint
        duration_ms: int | None = None
        frame_count: int | None = None
        backend = "opencv-stream"

        try:
            import cv2  # type: ignore[import-not-found]
        except ImportError:
            return VideoProbe(
                source_id=self.source_id,
                path=self.url,
                exists=True,
                is_file=False,
                width=None,
                height=None,
                fps=fps,
                duration_ms=None,
                frame_count=None,
                backend="fallback",
                warnings=("OpenCV is required for stream ingest.",),
            )

        capture = cv2.VideoCapture(self.url)
        try:
            if capture.isOpened():
                raw_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                raw_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                raw_fps = float(capture.get(cv2.CAP_PROP_FPS))
                raw_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
                width = raw_width if raw_width > 0 else None
                height = raw_height if raw_height > 0 else None
                fps = raw_fps if raw_fps > 0 else fps
                frame_count = raw_frame_count if raw_frame_count > 0 else None
                if frame_count and fps:
                    duration_ms = int((frame_count / fps) * 1000)
            else:
                warnings.append("OpenCV could not open this stream URL.")
        finally:
            capture.release()

        return VideoProbe(
            source_id=self.source_id,
            path=self.url,
            exists=True,
            is_file=False,
            width=width,
            height=height,
            fps=fps,
            duration_ms=duration_ms,
            frame_count=frame_count,
            backend=backend,
            warnings=tuple(warnings),
        )

    def iter_sampled_metadata(
        self,
        duration_ms: int | None = None,
        sample_every_ms: int = 1000,
        width: int | None = None,
        height: int | None = None,
    ) -> Iterator[FrameMetadata]:
        if sample_every_ms <= 0:
            raise ValueError("sample_every_ms must be greater than zero")
        probe = self.probe()
        effective_duration_ms = duration_ms if duration_ms is not None else probe.duration_ms
        effective_duration_ms = effective_duration_ms if effective_duration_ms is not None else 30 * 1000
        fps = probe.fps or self.fps_hint or 25.0
        frame_width = width or probe.width or 1920
        frame_height = height or probe.height or 1080
        wall_clock_ms = int(time.time() * 1000)
        for timestamp_ms in range(0, effective_duration_ms + 1, sample_every_ms):
            frame_number = int((timestamp_ms / 1000) * fps)
            yield FrameMetadata(
                frame_id=f"stream-frame-{frame_number}",
                source_id=self.source_id,
                source_type="stream_url",
                timestamp_ms=timestamp_ms,
                wall_clock_ms=wall_clock_ms,
                width=frame_width,
                height=frame_height,
                fps_hint=fps,
                ingest_latency_ms=0,
            )

    def iter_sampled_frames(
        self,
        duration_ms: int | None = None,
        sample_every_ms: int = 1000,
    ) -> Iterator[VideoFrameSample]:
        try:
            import cv2  # type: ignore[import-not-found]
        except ImportError as exc:
            raise SourceUnavailableError("OpenCV is required for stream frame sampling.") from exc

        probe = self.probe()
        fps = probe.fps or self.fps_hint or 25.0
        effective_duration_ms = duration_ms if duration_ms is not None else probe.duration_ms
        effective_duration_ms = effective_duration_ms if effective_duration_ms is not None else 30 * 1000
        capture = cv2.VideoCapture(self.url)
        if not capture.isOpened():
            capture.release()
            raise SourceUnavailableError(f"OpenCV could not open stream frames: {self.url}")

        try:
            for metadata in self.iter_sampled_metadata(
                duration_ms=effective_duration_ms,
                sample_every_ms=sample_every_ms,
                width=probe.width,
                height=probe.height,
            ):
                if probe.duration_ms is not None:
                    capture.set(cv2.CAP_PROP_POS_MSEC, metadata.timestamp_ms)
                ok, image = capture.read()
                if not ok or image is None:
                    continue
                yield VideoFrameSample(metadata=metadata, image=image)
                if probe.duration_ms is None:
                    time.sleep(max(0, sample_every_ms / 1000))
        finally:
            capture.release()
