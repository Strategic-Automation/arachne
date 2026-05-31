"""Read files."""

from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        sess_path = active_session_path.get()
        if sess_path:
            p = sess_path / "outputs" / p

    try:
        resolved_path = p.resolve()

        # Security constraint: path must be within cwd or active session outputs
        is_allowed = False
        if resolved_path.is_relative_to(Path.cwd().resolve()):
            is_allowed = True

        sess_path = active_session_path.get()
        if sess_path:
            outputs_dir = (sess_path / "outputs").resolve()
            if resolved_path.is_relative_to(outputs_dir):
                is_allowed = True

        if not is_allowed:
            return f"Error reading {path}: Access denied. Path is outside allowed directories."

        with open(resolved_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
