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
    resolved_path = Path(safe_path).resolve()
    cwd_resolved = Path.cwd().resolve()

    is_valid = False
    if resolved_path.is_relative_to(cwd_resolved):
        is_valid = True
    else:
        sess_path = active_session_path.get()
        if sess_path:
            sess_outputs_resolved = (sess_path / "outputs").resolve()
            if resolved_path.is_relative_to(sess_outputs_resolved):
                is_valid = True

    if not is_valid:
        return f"Error reading {path}: Access denied (path traversal)"

    try:
        with open(safe_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
