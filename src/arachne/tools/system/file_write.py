import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def is_safe_path(path: Path) -> bool:
    """Check if the path is within allowed directories."""
    resolved = path.resolve()
    allowed_dirs = [Path.cwd().resolve()]
    sess_path = active_session_path.get()
    if sess_path:
        allowed_dirs.append((sess_path / "outputs").resolve())
    return any(resolved.is_relative_to(d) for d in allowed_dirs)


def write_local_file(path: str, content: str) -> str:
    """Write content to a file. Defaults to session outputs if relative path."""
    p = Path(path)
    if not p.is_absolute():
        sess_path = active_session_path.get()
        if sess_path:
            p = sess_path / "outputs" / p

    if not is_safe_path(p):
        return f"Error: Path traversal detected. Access to {path} is denied."

    os.makedirs(p.parent, exist_ok=True)
    try:
        with open(p, "w") as f:
            f.write(content)
        return f"Successfully wrote {p}"
    except Exception as e:
        return f"Error writing {path}: {e}"
