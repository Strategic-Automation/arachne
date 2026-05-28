"""Write files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def write_local_file(path: str, content: str) -> str:
    """Write content to a file. Defaults to session outputs if relative path."""
    p = Path(path)
    allowed_bases = [Path.cwd().resolve()]

    sess_path = active_session_path.get()
    if sess_path:
        allowed_bases.append((sess_path / "outputs").resolve())

    if not p.is_absolute() and sess_path:
        p = sess_path / "outputs" / p

    safe_path = Path(os.path.realpath(str(p)))

    # Security: Prevent path traversal
    if not any(safe_path.is_relative_to(base) for base in allowed_bases):
        return f"Error writing {path}: Access denied. Path is outside allowed directories."

    os.makedirs(safe_path.parent, exist_ok=True)
    try:
        with open(safe_path, "w") as f:
            f.write(content)
        return f"Successfully wrote {safe_path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
