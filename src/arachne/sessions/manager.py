"""Session manager — persistent file-based session tracking."""

from __future__ import annotations

import json
import os
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

active_session_path: ContextVar[Path | None] = ContextVar("active_session_path", default=None)


class Session:
    def __init__(self, session_id: str, base_dir: str | Path | None = None) -> None:
        self._id = session_id
        self._dir = (Path(base_dir) if base_dir else _default_dir()) / session_id
        self._dir.mkdir(parents=True, exist_ok=True)
        # Set the active session path for this context
        active_session_path.set(self._dir)

    @property
    def id(self) -> str:
        return self._id

    @property
    def path(self) -> Path:
        return self._dir

    # ── Graph ─────────────────────────────────────────────────────────

    def save_graph(self, topology_dict: dict) -> None:
        """Save the woven topology as read-only YAML/JSON."""
        path = self._dir / "graph.json"
        with open(path, "w") as f:
            json.dump(topology_dict, f, indent=2, default=str)

    # ── State ─────────────────────────────────────────────────────────

    def save_state(self, state: dict) -> None:
        """Write mutable execution state (node statuses, progress)."""
        with open(self._dir / "state.json", "w") as f:
            json.dump(state, f, indent=2)

    # ── Inputs / Artifacts ────────────────────────────────────────────

    def save_inputs(self, inputs: dict) -> None:
        with open(self._dir / "inputs.json", "w") as f:
            json.dump(inputs, f, indent=2, default=str)

    def load_inputs(self) -> dict | None:
        path = self._dir / "inputs.json"
        return json.loads(path.read_text()) if path.exists() else None

    # ── Logs ──────────────────────────────────────────────────────────

    def append_log(self, node_id: str, message: str) -> None:
        log_dir = self._dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / f"{node_id}.log", "a") as f:
            ts = datetime.now(UTC).isoformat()
            f.write(f"[{ts}] {message}\n")

    # ── Node Outputs ─────────────────────────────────────────────────

    def save_node_output(self, node_id: str, output: dict | str) -> None:
        """Save a single node's output to <session_dir>/outputs/{node_id}.json."""
        outputs_dir = self._dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        path = outputs_dir / f"{node_id}.json"
        data = {"node_id": node_id, "output": output}
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def load_outputs(self) -> dict[str, dict]:
        """Load all saved node outputs from <session_dir>/outputs/."""
        outputs_dir = self._dir / "outputs"
        if not outputs_dir.exists():
            return {}
        result = {}
        try:
            with os.scandir(outputs_dir) as it:
                for entry in it:
                    if entry.name.endswith(".json") and entry.is_file():
                        try:
                            with open(entry.path, "rb") as f:
                                data = json.load(f)
                            node_id = data.get("node_id")
                            if node_id:
                                result[node_id] = data
                        except (json.JSONDecodeError, OSError):
                            pass
        except FileNotFoundError:
            pass
        return result

    # ── Spillover ─────────────────────────────────────────────────────

    def get_spillover_dir(self) -> Path:
        """Get the per-session spillover directory."""
        spill_dir = self._dir / "spillover"
        spill_dir.mkdir(parents=True, exist_ok=True)
        return spill_dir


def _default_dir() -> Path:
    return Path.home() / ".local" / "share" / "arachne" / "sessions"


def find_latest_session_by_goal(goal: str, base_dir: str | Path | None = None) -> str | None:
    """Find the most recent session ID that matches the given goal."""
    directory = Path(base_dir) if base_dir else _default_dir()
    if not directory.exists():
        return None

    entries = []
    try:
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_dir():
                    entries.append((entry.path, entry.stat().st_mtime, entry.name))
    except FileNotFoundError:
        return None

    # Sort by mtime descending (most recent first)
    entries.sort(key=lambda x: x[1], reverse=True)

    for path, _, name in entries:
        inputs_path = os.path.join(path, "inputs.json")
        try:
            with open(inputs_path, "rb") as f:
                inputs = json.load(f)
                if inputs.get("goal") == goal:
                    return name
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue

    return None
