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

    safe_path = Path(os.path.realpath(str(p))).resolve()
    cwd_path = Path.cwd().resolve()
    sess_outputs_path = (sess_path / "outputs").resolve() if sess_path else None

    is_safe = False
    if safe_path.is_relative_to(cwd_path) or (sess_outputs_path and safe_path.is_relative_to(sess_outputs_path)):
        is_safe = True

    if not is_safe:
        return f"Error writing {path}: Access denied. Path must be relative to {cwd_path} or session outputs."

    os.makedirs(safe_path.parent, exist_ok=True)
    try:
        with open(str(safe_path), "w") as f:
            f.write(content)
        return f"Successfully wrote {safe_path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
