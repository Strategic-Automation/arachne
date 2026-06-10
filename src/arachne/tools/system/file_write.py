"""Write files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def write_local_file(path: str, content: str) -> str:
    """Write content to a file. Defaults to session outputs if relative path."""
    p = Path(path)
    if not p.is_absolute():
        sess_path = active_session_path.get()
        if sess_path:
            p = (sess_path / "outputs").resolve() / p

    safe_path = p.resolve()

    # Security Check: Ensure path is within allowed boundaries
    is_safe = False
    if safe_path.is_relative_to(Path.cwd().resolve()):
        is_safe = True
    else:
        sess_path = active_session_path.get()
        if sess_path and safe_path.is_relative_to((sess_path / "outputs").resolve()):
            is_safe = True

    if not is_safe:
        return f"Error writing {path}: Path traversal detected or path outside allowed boundaries."

    os.makedirs(safe_path.parent, exist_ok=True)
    try:
        with open(safe_path, "w") as f:
            f.write(content)
        return f"Successfully wrote {safe_path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
