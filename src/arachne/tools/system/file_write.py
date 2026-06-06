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
            p = sess_path / "outputs" / p

    resolved_path = p.resolve()
    cwd_resolved = Path.cwd().resolve()

    is_valid = False
    if resolved_path.is_relative_to(cwd_resolved):
        is_valid = True
    else:
        sess_path = active_session_path.get()
        if sess_path:
            sess_outputs_resolved = (sess_path / "outputs").resolve()
            if resolved_path.is_relative_to(sess_outputs_resolved):
                is_valid = True

    if not is_valid:
        return f"Error writing {path}: Access denied (path traversal)"

    os.makedirs(p.parent, exist_ok=True)
    try:
        with open(p, "w") as f:
            f.write(content)
        return f"Successfully wrote {p}"
    except Exception as e:
        return f"Error writing {path}: {e}"
