"""Session status tools."""

import json
from pathlib import Path

_SESSIONS_DIR = Path.home() / ".local" / "share" / "arachne" / "sessions"


def list_sessions() -> str:
    """List all Arachne session IDs, their goals, and current status."""
    if not _SESSIONS_DIR.exists():
        return "No sessions found."

    sessions = []
    for d in sorted(_SESSIONS_DIR.iterdir()):
        if not d.is_dir() or not d.name.startswith("run_"):
            continue
        state_path = d / "state.json"
        inputs_path = d / "inputs.json"
        graph_path = d / "graph.json"
        status = "unknown"
        goal = "unknown"
        graph_name = "unknown"
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text())
                status = state.get("status", "unknown")
            except json.JSONDecodeError:
                pass
        if inputs_path.exists():
            try:
                inputs = json.loads(inputs_path.read_text())
                goal = inputs.get("goal", "unknown")
            except json.JSONDecodeError:
                pass
        if graph_path.exists():
            try:
                graph = json.loads(graph_path.read_text())
                graph_name = graph.get("name", "unknown")
            except json.JSONDecodeError:
                pass
        sessions.append((d.name, goal, graph_name, status))

    if not sessions:
        return "No sessions found."

    lines = [f"Sessions ({len(sessions)} total):"]
    for sid, goal, graph, status in sessions:
        lines.append(f"  {sid}")
        lines.append(f"    Goal: {goal}")
        lines.append(f"    Graph: {graph}")
        lines.append(f"    Status: {status}")
    return "\n".join(lines)


def get_session_status(session_id: str) -> str:
    """Get the current execution status of a specific session."""
    session_dir = _SESSIONS_DIR / session_id
    if not session_dir.exists():
        return f"Session '{session_id}' not found."

    result = {}
    state_path = session_dir / "state.json"
    if state_path.exists():
        result["state"] = json.loads(state_path.read_text())
    graph_path = session_dir / "graph.json"
    if graph_path.exists():
        result["graph"] = json.loads(graph_path.read_text())
    inputs_path = session_dir / "inputs.json"
    if inputs_path.exists():
        result["inputs"] = json.loads(inputs_path.read_text())

    logs_dir = session_dir / "logs"
    if logs_dir.exists():
        result["logs"] = {}
        for log_file in logs_dir.iterdir():
            if log_file.suffix == ".log":
                result["logs"][log_file.stem] = log_file.read_text()

    return json.dumps(result, indent=2)
