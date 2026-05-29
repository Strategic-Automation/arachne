"""Read files."""

from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)
    sess_path = active_session_path.get()

    if not p.is_absolute() and not p.exists() and sess_path:
        p = sess_path / "outputs" / p

    resolved = p.resolve()
    # Security: Prevent path traversal by constraining to CWD or session outputs
    is_safe = resolved.is_relative_to(Path.cwd().resolve())
    if sess_path and not is_safe:
        is_safe = resolved.is_relative_to((sess_path / "outputs").resolve())

    if not is_safe:
        return f"Error: Access denied. Path {path} is outside allowed boundaries."

    try:
        with open(resolved, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
