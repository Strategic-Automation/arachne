"""Read files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)
    sess_path = active_session_path.get()

    if not p.is_absolute() and not p.exists():
        if sess_path:
            p = sess_path / "outputs" / p

    resolved_path = p.resolve()

    is_safe = False
    if resolved_path.is_relative_to(Path.cwd()):
        is_safe = True
    elif sess_path and resolved_path.is_relative_to(sess_path / "outputs"):
        is_safe = True

    if not is_safe:
        return f"Error reading {path}: Access denied"

    try:
        with open(resolved_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
