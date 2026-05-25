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

    # SECURITY: Prevent path traversal by restricting access to allowed directories
    try:
        resolved = Path(os.path.realpath(str(p))).resolve()
        allowed_dirs = [Path.cwd().resolve()]
        if sess_path:
            allowed_dirs.append((sess_path / "outputs").resolve())

        if not any(resolved.is_relative_to(d) for d in allowed_dirs):
            return f"Security Error: Path access denied for {path}"
    except Exception:
        return f"Security Error: Invalid path {path}"

    os.makedirs(p.parent, exist_ok=True)
    try:
        with open(p, "w") as f:
            f.write(content)
        return f"Successfully wrote {p}"
    except Exception as e:
        return f"Error writing {path}: {e}"
