from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Iterator

from project_fm.domain import TacticalState


class InvalidMatchId(ValueError):
    pass


MATCH_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


class MatchStateStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_match_path(self, match_id: str, create: bool = False) -> Path:
        if not MATCH_ID_PATTERN.fullmatch(match_id) or ".." in match_id.split("."):
            raise InvalidMatchId("match_id must be 1-80 characters using letters, numbers, dots, dashes, or underscores")
        path = (self.root / match_id).resolve()
        if path != self.root and self.root not in path.parents:
            raise InvalidMatchId("match_id resolved outside the data root")
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def match_dir(self, match_id: str) -> Path:
        return self._safe_match_path(match_id, create=True)

    def states_path(self, match_id: str) -> Path:
        return self.match_dir(match_id) / "tactical_states.jsonl"

    def manifest_path(self, match_id: str) -> Path:
        return self.match_dir(match_id) / "manifest.json"

    def corrections_path(self, match_id: str) -> Path:
        return self.match_dir(match_id) / "track_corrections.json"

    def append_state(self, state: TacticalState) -> None:
        path = self.states_path(state.match_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(state.model_dump_json())
            handle.write("\n")

    def replace_states(self, match_id: str, states: list[TacticalState]) -> None:
        path = self.states_path(match_id)
        with path.open("w", encoding="utf-8") as handle:
            for state in states:
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

    def latest_state(self, match_id: str) -> TacticalState | None:
        latest: TacticalState | None = None
        for state in self.iter_states(match_id):
            latest = state
        return latest

    def list_match_ids(self) -> list[str]:
        if not self.root.exists():
            return []
        match_ids: list[str] = []
        for path in self.root.iterdir():
            if path.is_dir() and (path / "tactical_states.jsonl").exists():
                match_ids.append(path.name)
        return sorted(match_ids)

    def state_count(self, match_id: str) -> int:
        return sum(1 for _ in self.iter_states(match_id))

    def write_manifest(self, match_id: str, manifest: dict[str, object]) -> None:
        path = self.manifest_path(match_id)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")

    def read_manifest(self, match_id: str) -> dict[str, object] | None:
        path = self.manifest_path(match_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        return loaded if isinstance(loaded, dict) else None

    def read_corrections(self, match_id: str) -> dict[str, dict[str, object]]:
        path = self.corrections_path(match_id)
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, dict):
            return {}
        return {str(track_id): correction for track_id, correction in loaded.items() if isinstance(correction, dict)}

    def write_corrections(self, match_id: str, corrections: dict[str, dict[str, object]]) -> None:
        path = self.corrections_path(match_id)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(corrections, handle, indent=2, sort_keys=True)
            handle.write("\n")

    def prune_corrections(self, match_id: str, valid_track_ids: set[str]) -> int:
        corrections = self.read_corrections(match_id)
        if not corrections:
            return 0
        pruned = {
            track_id: correction
            for track_id, correction in corrections.items()
            if track_id in valid_track_ids
        }
        removed = len(corrections) - len(pruned)
        if removed > 0:
            self.write_corrections(match_id, pruned)
        return removed

    def upsert_correction(self, match_id: str, track_id: str, correction: dict[str, object]) -> dict[str, object]:
        corrections = self.read_corrections(match_id)
        corrections[track_id] = correction
        self.write_corrections(match_id, corrections)
        return correction

    def delete_correction(self, match_id: str, track_id: str) -> bool:
        corrections = self.read_corrections(match_id)
        if track_id not in corrections:
            return False
        del corrections[track_id]
        self.write_corrections(match_id, corrections)
        return True

    def delete_match(self, match_id: str) -> bool:
        path = self._safe_match_path(match_id)
        if not path.exists():
            return False
        shutil.rmtree(path)
        return True
