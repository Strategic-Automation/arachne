"""Read files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)

    sess_path = active_session_path.get()

    if p.is_absolute():
        # Prevent absolute paths from escaping the intended sandbox
        target_path = p.resolve()
        base_dir = (sess_path / "outputs").resolve() if sess_path else Path.cwd().resolve()
    else:
        if not p.exists() and sess_path:
            base_dir = (sess_path / "outputs").resolve()
            target_path = (base_dir / p).resolve()
        else:
            base_dir = Path.cwd().resolve()
            target_path = (base_dir / p).resolve()

    if not target_path.is_relative_to(base_dir):
        return f"Error: Path traversal detected. Access to {path} is denied."
    p = target_path

    safe_path = os.path.realpath(str(p))
    try:
        with open(safe_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
