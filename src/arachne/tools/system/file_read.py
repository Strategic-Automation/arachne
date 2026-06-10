"""Read files."""

from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        sess_path = active_session_path.get()
        if sess_path:
            p = (sess_path / "outputs").resolve() / p

    safe_path = p.resolve()

    # Security Check: Ensure path is within allowed boundaries
    is_safe = False
    if safe_path.is_relative_to(Path.cwd().resolve()):
        is_safe = True
    else:
        sess_path = active_session_path.get()
        if sess_path and safe_path.is_relative_to((sess_path / "outputs").resolve()):
            is_safe = True

    if not is_safe:
        return f"Error reading {path}: Path traversal detected or path outside allowed boundaries."

    try:
        with open(safe_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
