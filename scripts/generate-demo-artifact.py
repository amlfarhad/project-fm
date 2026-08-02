#!/usr/bin/env python3
"""Generate the hosted demo artifact by running the real OpenCV pipeline."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from project_fm.api import (  # noqa: E402
    ProcessFileRequest,
    get_store,
    run_process_file,
    summarize_match,
)


def main() -> None:
    sample_path = ROOT / "frontend" / "public" / "samples" / "galatasaray-steau-2008-12s.mp4"
    output_path = ROOT / "frontend" / "public" / "samples" / "galatasaray-steau-2008-12s.states.json"
    if not sample_path.is_file():
        raise SystemExit(f"Missing sample video: {sample_path}")

    with tempfile.TemporaryDirectory(prefix="project-fm-artifact-") as data_root:
        os.environ["PROJECT_FM_DATA_ROOT"] = data_root
        started_at = time.perf_counter()
        result = run_process_file(
            match_id="commons-galatasaray-2008",
            request=ProcessFileRequest(
                path=str(sample_path),
                duration_ms=12_000,
                sample_every_ms=1000,
                fps_hint=30.0,
                replace_existing=True,
                use_cache=False,
            ),
        )
        summary = summarize_match(get_store(), "commons-galatasaray-2008")
        provenance = result.provenance.model_copy(
            update={
                "execution_mode": "precomputed_pipeline",
                "pipeline_commit": os.environ.get("PROJECT_FM_PIPELINE_COMMIT", "34c4397"),
            }
        )
        states = [state.model_dump(mode="json") for state in get_store().iter_states("commons-galatasaray-2008")]
        artifact = {
            "artifact_version": 1,
            "generated_by": "scripts/generate-demo-artifact.py",
            "generated_elapsed_ms": round((time.perf_counter() - started_at) * 1000),
            "sample_id": "commons-galatasaray-2008",
            "video_url": "/samples/galatasaray-steau-2008-12s.mp4",
            "provenance": provenance.model_dump(mode="json"),
            "summary": summary.model_copy(update={"provenance": provenance}).model_dump(mode="json"),
            "states": states,
        }
        output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(output_path), "states": len(states), "processor_backend": result.processor_backend}))


if __name__ == "__main__":
    main()
