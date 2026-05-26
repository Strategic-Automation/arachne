"""Write files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def write_local_file(path: str, content: str) -> str:
    """Write content to a file. Defaults to session outputs if relative path."""
    p = Path(path)

    # Get allowed directories for security check
    allowed_dirs = [Path.cwd().resolve()]
    sess_path = active_session_path.get()

    if sess_path:
        outputs_dir = (sess_path / "outputs").resolve()
        allowed_dirs.append(outputs_dir)

        if not p.is_absolute():
            p = sess_path / "outputs" / p

    # Security Check: Prevent path traversal
    try:
        resolved_path = p.resolve()
        is_safe = any(resolved_path.is_relative_to(allowed) for allowed in allowed_dirs)
        if not is_safe:
            return f"Security Error: Access to {path} is denied. Paths must be within the current working directory or session outputs."
    except Exception as e:
        return f"Error resolving path {path}: {e}"

    os.makedirs(resolved_path.parent, exist_ok=True)
    try:
        with open(resolved_path, "w") as f:
            f.write(content)
        return f"Successfully wrote {resolved_path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
