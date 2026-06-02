"""Read files."""

from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)
    base_path = Path.cwd().resolve()

    if not p.is_absolute() and not p.exists():
        sess_path = active_session_path.get()
        if sess_path:
            base_path = (sess_path / "outputs").resolve()
            p = base_path / p

    try:
        resolved_path = p.resolve()
        if not resolved_path.is_relative_to(base_path):
            return f"Error reading {path}: Access denied. Path traversal detected."

        with open(resolved_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
