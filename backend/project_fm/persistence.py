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
