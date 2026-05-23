"""Write files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def write_local_file(path: str, content: str) -> str:
    """Write content to a file. Defaults to session outputs if relative path."""
    p = Path(path)

    sess_path = active_session_path.get()

    if p.is_absolute():
        # Prevent absolute paths from escaping the intended sandbox
        target_path = p.resolve()
        base_dir = (sess_path / "outputs").resolve() if sess_path else Path.cwd().resolve()
    else:
        if sess_path:
            base_dir = (sess_path / "outputs").resolve()
        else:
            base_dir = Path.cwd().resolve()

        target_path = (base_dir / p).resolve()

    if not target_path.is_relative_to(base_dir):
        return f"Error: Path traversal detected. Access to {path} is denied."
    p = target_path

    os.makedirs(p.parent, exist_ok=True)
    try:
        with open(p, "w") as f:
            f.write(content)
        return f"Successfully wrote {p}"
    except Exception as e:
        return f"Error writing {path}: {e}"
