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

    resolved = p.resolve()
    # Security: Prevent path traversal by constraining to CWD or session outputs
    is_safe = resolved.is_relative_to(Path.cwd().resolve())
    if sess_path and not is_safe:
        is_safe = resolved.is_relative_to((sess_path / "outputs").resolve())

    if not is_safe:
        return f"Error: Access denied. Path {path} is outside allowed boundaries."

    os.makedirs(resolved.parent, exist_ok=True)
    try:
        with open(resolved, "w") as f:
            f.write(content)
        return f"Successfully wrote {p}"
    except Exception as e:
        return f"Error writing {path}: {e}"
