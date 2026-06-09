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

    safe_path = Path(os.path.realpath(str(p))).resolve()
    cwd_path = Path.cwd().resolve()
    sess_outputs_path = (sess_path / "outputs").resolve() if sess_path else None

    is_safe = False
    if safe_path.is_relative_to(cwd_path) or (sess_outputs_path and safe_path.is_relative_to(sess_outputs_path)):
        is_safe = True

    if not is_safe:
        return f"Error reading {path}: Access denied. Path must be relative to {cwd_path} or session outputs."

    try:
        with open(str(safe_path), errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
