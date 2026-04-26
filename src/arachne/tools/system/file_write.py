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

    os.makedirs(p.parent, exist_ok=True)
    try:
        with open(p, "w") as f:
            f.write(content)
        return f"Successfully wrote {p}"
    except Exception as e:
        return f"Error writing {path}: {e}"
