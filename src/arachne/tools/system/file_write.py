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

    try:
        resolved_path = p.resolve()

        # Security constraint: path must be within cwd or active session outputs
        is_allowed = False
        if resolved_path.is_relative_to(Path.cwd().resolve()):
            is_allowed = True

        sess_path = active_session_path.get()
        if sess_path:
            outputs_dir = (sess_path / "outputs").resolve()
            if resolved_path.is_relative_to(outputs_dir):
                is_allowed = True

        if not is_allowed:
            return f"Error writing {path}: Access denied. Path is outside allowed directories."

        os.makedirs(resolved_path.parent, exist_ok=True)

        with open(resolved_path, "w") as f:
            f.write(content)
        return f"Successfully wrote {resolved_path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
