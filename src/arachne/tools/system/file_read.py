"""Read files."""

from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)
    is_absolute = p.is_absolute()

    if not is_absolute and not p.exists():
        sess_path = active_session_path.get()
        if sess_path:
            p = sess_path / "outputs" / p

    try:
        resolved_path = p.resolve()

        is_safe = resolved_path.is_relative_to(Path.cwd())
        sess_path = active_session_path.get()
        if not is_safe and sess_path:
            is_safe = resolved_path.is_relative_to((sess_path / "outputs").resolve())

        if not is_safe:
            return f"Security Error: Access to {path} is restricted to current directory and session outputs."

        with open(resolved_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
