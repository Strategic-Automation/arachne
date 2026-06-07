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

    # Security boundary check
    try:
        resolved_path = p.resolve()
        cwd_resolved = Path.cwd().resolve()
        is_safe = resolved_path.is_relative_to(cwd_resolved)

        if sess_path and not is_safe:
            sess_outputs_resolved = (sess_path / "outputs").resolve()
            is_safe = resolved_path.is_relative_to(sess_outputs_resolved)

        if not is_safe:
            return f"Security Error: Access denied to path {path} outside allowed boundaries."
    except Exception as e:
        return f"Security Error: Path resolution failed for {path}: {e}"

    os.makedirs(p.parent, exist_ok=True)
    try:
        with open(p, "w") as f:
            f.write(content)
        return f"Successfully wrote {p}"
    except Exception as e:
        return f"Error writing {path}: {e}"
