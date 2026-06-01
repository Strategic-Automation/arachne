"""Write files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def write_local_file(path: str, content: str) -> str:
    """Write content to a file. Defaults to session outputs if relative path."""
    p = Path(path)
    sess_path = active_session_path.get()
    if not p.is_absolute() and sess_path:
        p = sess_path / "outputs" / p

    resolved_path = p.resolve()

    is_safe = False
    if resolved_path.is_relative_to(Path.cwd()) or (sess_path and resolved_path.is_relative_to(sess_path / "outputs")):
        is_safe = True

    if not is_safe:
        return f"Error writing {path}: Access denied"

    os.makedirs(resolved_path.parent, exist_ok=True)
    try:
        with open(resolved_path, "w") as f:
            f.write(content)
        return f"Successfully wrote {resolved_path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
