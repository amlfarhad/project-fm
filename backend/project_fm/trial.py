from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_fm.api import ProcessFileRequest, run_process_file, summarize_match
from project_fm.config import get_settings
from project_fm.persistence import MatchStateStore


@dataclass(frozen=True)
class TrialThresholds:
    min_states: int = 2
    min_observed_players: int = 6
    min_calibration_confidence: float = 0.6
    min_processing_fps: float = 1.0
    min_identity_coverage: float = 0.0
    min_observed_identity_coverage: float = 0.0


def evaluate_trial(summary: Any, thresholds: TrialThresholds) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if summary.states < thresholds.min_states:
        failures.append(f"states<{thresholds.min_states}")
    if (summary.observed_players or 0) < thresholds.min_observed_players:
        failures.append(f"observed_players<{thresholds.min_observed_players}")
    if summary.system_confidence is None or summary.system_confidence <= 0:
        failures.append("system_confidence_missing")
    if (
        summary.calibration_confidence is None
        or summary.calibration_confidence < thresholds.min_calibration_confidence
    ):
        failures.append(f"calibration_confidence<{thresholds.min_calibration_confidence}")
    if summary.processor_backend == "baseline-fallback":
        failures.append("baseline_fallback_not_gtm_ready")
    if summary.processing_fps is None or summary.processing_fps < thresholds.min_processing_fps:
        failures.append(f"processing_fps<{thresholds.min_processing_fps}")
    if summary.identity_coverage is None or summary.identity_coverage < thresholds.min_identity_coverage:
        failures.append(f"identity_coverage<{thresholds.min_identity_coverage}")
    if (
        summary.observed_identity_coverage is None
        or summary.observed_identity_coverage < thresholds.min_observed_identity_coverage
    ):
        failures.append(f"observed_identity_coverage<{thresholds.min_observed_identity_coverage}")

    latest = get_settings().data_root / summary.match_id / "tactical_states.jsonl"
    if not latest.exists():
        failures.append("state_file_missing")
    return not failures, failures


def run_trial(args: argparse.Namespace) -> dict[str, object]:
    request = ProcessFileRequest(
        path=args.path,
        source_type=args.source_type,
        stream_url=args.stream_url,
        duration_ms=args.duration_ms,
        sample_every_ms=args.sample_every_ms,
        fps_hint=args.fps_hint,
        replace_existing=True,
        use_cache=False,
    )
    result = run_process_file(match_id=args.match_id, request=request)
    summary = summarize_match(MatchStateStore(get_settings().data_root), args.match_id)
    thresholds = TrialThresholds(
        min_states=args.min_states,
        min_observed_players=args.min_observed_players,
        min_calibration_confidence=args.min_calibration_confidence,
        min_processing_fps=args.min_processing_fps,
        min_identity_coverage=args.min_identity_coverage,
        min_observed_identity_coverage=args.min_observed_identity_coverage,
    )
    passed, failures = evaluate_trial(summary, thresholds)
    quality_warnings = list(summary.quality_warnings)
    trial_status = "fail" if not passed else "pass_with_warnings" if quality_warnings else "pass"
    return {
        "passed": passed,
        "trial_status": trial_status,
        "failures": failures,
        "quality_warnings": quality_warnings,
        "result": result.model_dump(),
        "summary": summary.model_dump(),
        "thresholds": thresholds.__dict__,
    }

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Project FM GTM trial against a file or stream source.")
    parser.add_argument("--match-id", default="trial")
    parser.add_argument("--path")
    parser.add_argument("--source-type", choices=["file", "stream_url"], default="file")
    parser.add_argument("--stream-url")
    parser.add_argument("--duration-ms", type=int)
    parser.add_argument("--sample-every-ms", type=int, default=1000)
    parser.add_argument("--fps-hint", type=float)
    parser.add_argument("--min-states", type=int, default=2)
    parser.add_argument("--min-observed-players", type=int, default=6)
    parser.add_argument("--min-calibration-confidence", type=float, default=0.6)
    parser.add_argument("--min-processing-fps", type=float, default=1.0)
    parser.add_argument("--min-identity-coverage", type=float, default=0.0)
    parser.add_argument("--min-observed-identity-coverage", type=float, default=0.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = run_trial(args)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
