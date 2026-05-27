"""Read files."""

from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)

    # Try session outputs directory first for relative paths if file doesn't exist locally
    sess_path = active_session_path.get()
    if not p.is_absolute() and not p.exists() and sess_path:
        p = sess_path / "outputs" / p

    # Security check: Prevent path traversal by strictly enforcing boundaries
    try:
        resolved_path = p.resolve()
        cwd = Path.cwd().resolve()

        is_safe = resolved_path.is_relative_to(cwd)
        if sess_path and not is_safe:
            is_safe = resolved_path.is_relative_to((sess_path / "outputs").resolve())

        if not is_safe:
            return f"Security Error: Access to path '{path}' is denied. Outside of allowed directories."
    except Exception as e:
        return f"Security Error resolving path '{path}': {e}"

    try:
        with open(resolved_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
