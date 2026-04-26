"""Graph lifecycle tools."""

import json
from pathlib import Path

_SESSIONS_DIR = Path.home() / ".local" / "share" / "arachne" / "sessions"


def save_checkpoint(session_id: str, node_id: str, state: dict) -> str:
    """Save the execution state of a node for crash recovery."""
    path = _SESSIONS_DIR / session_id / "checkpoints" / f"{node_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))
    return f"Checkpoint saved to {path}"


def load_checkpoint(session_id: str, node_id: str) -> str:
    """Load a previously saved checkpoint for a node."""
    path = _SESSIONS_DIR / session_id / "checkpoints" / f"{node_id}.json"
    if not path.exists():
        return f"No checkpoint found for node '{node_id}' in session '{session_id}'"
    return path.read_text()


def list_checkpoints(session_id: str) -> str:
    """List all checkpoints for a session."""
    ckpt_dir = _SESSIONS_DIR / session_id / "checkpoints"
    if not ckpt_dir.exists():
        return f"No checkpoints found for session '{session_id}'"
    checkpoints = [f.stem for f in ckpt_dir.iterdir() if f.suffix == ".json"]
    if not checkpoints:
        return f"No checkpoints found for session '{session_id}'"
    return f"Checkpoints for {session_id}: {', '.join(checkpoints)}"
