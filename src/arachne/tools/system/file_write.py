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

    # Security check: Prevent path traversal by strictly enforcing boundaries
    try:
        resolved_path = p.resolve()
        cwd = Path.cwd().resolve()

        is_safe = resolved_path.is_relative_to(cwd)
        if sess_path and not is_safe:
            is_safe = resolved_path.is_relative_to((sess_path / "outputs").resolve())

        if not is_safe:
            return f"Security Error: Access to path '{path}' is denied. Outside of allowed directories."
    except Exception as e:
        return f"Security Error resolving path '{path}': {e}"

    os.makedirs(resolved_path.parent, exist_ok=True)
    try:
        with open(resolved_path, "w") as f:
            f.write(content)
        return f"Successfully wrote {resolved_path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
