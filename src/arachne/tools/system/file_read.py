"""Read files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)
    sess_path = active_session_path.get()

    if not p.is_absolute() and not p.exists() and sess_path:
        p = sess_path / "outputs" / p

    # Security: Prevent path traversal
    resolved = p.resolve()
    cwd_resolved = Path.cwd().resolve()

    is_safe = False
    if resolved.is_relative_to(cwd_resolved):
        is_safe = True
    elif sess_path:
        sess_outputs_resolved = (sess_path / "outputs").resolve()
        if resolved.is_relative_to(sess_outputs_resolved):
            is_safe = True

    if not is_safe:
        return f"Error reading {path}: Access denied (path traversal outside allowed directories)"

    safe_path = os.path.realpath(str(p))
    try:
        with open(safe_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
