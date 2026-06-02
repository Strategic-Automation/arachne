"""Write files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def write_local_file(path: str, content: str) -> str:
    """Write content to a file. Defaults to session outputs if relative path."""
    p = Path(path)
    base_path = Path.cwd().resolve()

    if not p.is_absolute():
        sess_path = active_session_path.get()
        if sess_path:
            base_path = (sess_path / "outputs").resolve()
            p = base_path / p

    try:
        resolved_path = p.resolve()
        if not resolved_path.is_relative_to(base_path):
            return f"Error writing {path}: Access denied. Path traversal detected."

        os.makedirs(resolved_path.parent, exist_ok=True)
        with open(resolved_path, "w") as f:
            f.write(content)
        return f"Successfully wrote {resolved_path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
