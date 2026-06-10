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
