"""Read files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        sess_path = active_session_path.get()
        if sess_path:
            p = sess_path / "outputs" / p

    safe_path = os.path.realpath(str(p))
    try:
        with open(safe_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
