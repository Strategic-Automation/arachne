"""Read files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)
    allowed_bases = [Path.cwd().resolve()]

    sess_path = active_session_path.get()
    if sess_path:
        allowed_bases.append((sess_path / "outputs").resolve())

    if not p.is_absolute() and not p.exists() and sess_path:
        p = sess_path / "outputs" / p

    safe_path = Path(os.path.realpath(str(p)))

    # Security: Prevent path traversal
    if not any(safe_path.is_relative_to(base) for base in allowed_bases):
        return f"Error reading {path}: Access denied. Path is outside allowed directories."

    try:
        with open(safe_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
