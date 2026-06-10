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

    # Security: Prevent path traversal
    resolved = p.resolve()
    cwd_resolved = Path.cwd().resolve()

    is_safe = False
    if resolved.is_relative_to(cwd_resolved):
        is_safe = True
    elif sess_path:
        sess_outputs_resolved = (sess_path / "outputs").resolve()
        if resolved.is_relative_to(sess_outputs_resolved):
            is_safe = True

    if not is_safe:
        return f"Error writing {path}: Access denied (path traversal outside allowed directories)"

    os.makedirs(p.parent, exist_ok=True)
    try:
        with open(p, "w") as f:
            f.write(content)
        return f"Successfully wrote {p}"
    except Exception as e:
        return f"Error writing {path}: {e}"
