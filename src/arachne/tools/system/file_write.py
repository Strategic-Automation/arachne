"""Write files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def write_local_file(path: str, content: str) -> str:
    """Write content to a file. Defaults to session outputs if relative path."""
    p = Path(path)
    is_absolute = p.is_absolute()

    if not is_absolute:
        sess_path = active_session_path.get()
        if sess_path:
            p = sess_path / "outputs" / p

    try:
        resolved_path = p.resolve()

        is_safe = resolved_path.is_relative_to(Path.cwd())
        sess_path = active_session_path.get()
        if not is_safe and sess_path:
            is_safe = resolved_path.is_relative_to((sess_path / "outputs").resolve())

        if not is_safe:
            return f"Security Error: Write access to {path} is restricted to current directory and session outputs."

        os.makedirs(resolved_path.parent, exist_ok=True)
        with open(resolved_path, "w") as f:
            f.write(content)
        return f"Successfully wrote {p}"
    except Exception as e:
        return f"Error writing {path}: {e}"
