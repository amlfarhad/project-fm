from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_root: Path
    detector_backend: str
    yolo_model_path: Path | None
    api_token: str | None


def get_settings() -> Settings:
    root = Path(os.environ.get("PROJECT_FM_DATA_ROOT", "data")).resolve()
    detector_backend = os.environ.get("PROJECT_FM_DETECTOR", "opencv").strip().lower()
    model = os.environ.get("PROJECT_FM_YOLO_MODEL")
    return Settings(
        data_root=root,
        detector_backend=detector_backend,
        yolo_model_path=Path(model).expanduser().resolve() if model else None,
        api_token=os.environ.get("PROJECT_FM_API_TOKEN"),
    )
