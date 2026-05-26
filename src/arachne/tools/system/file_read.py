"""Read files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)

    # Get allowed directories for security check
    allowed_dirs = [Path.cwd().resolve()]
    sess_path = active_session_path.get()

    if sess_path:
        outputs_dir = (sess_path / "outputs").resolve()
        allowed_dirs.append(outputs_dir)

        # If relative and doesn't exist in cwd, try outputs dir
        if not p.is_absolute() and not p.exists():
            p = sess_path / "outputs" / p

    # Security Check: Prevent path traversal
    try:
        resolved_path = p.resolve()
        is_safe = any(resolved_path.is_relative_to(allowed) for allowed in allowed_dirs)
        if not is_safe:
            return f"Security Error: Access to {path} is denied. Paths must be within the current working directory or session outputs."
    except Exception as e:
        return f"Error resolving path {path}: {e}"

    safe_path = os.path.realpath(str(resolved_path))
    try:
        with open(safe_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
