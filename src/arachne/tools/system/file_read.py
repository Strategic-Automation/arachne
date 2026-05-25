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

    safe_path = os.path.realpath(str(p))

    # SECURITY: Prevent path traversal by restricting access to allowed directories
    try:
        resolved = Path(safe_path).resolve()
        allowed_dirs = [Path.cwd().resolve()]
        if sess_path:
            allowed_dirs.append((sess_path / "outputs").resolve())

        if not any(resolved.is_relative_to(d) for d in allowed_dirs):
            return f"Security Error: Path access denied for {path}"
    except Exception:
        return f"Security Error: Invalid path {path}"

    try:
        with open(safe_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
