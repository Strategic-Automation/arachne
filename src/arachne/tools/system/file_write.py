"""Write files."""

import os
from pathlib import Path

from arachne.sessions.manager import active_session_path


def write_local_file(path: str, content: str) -> str:
    """Write content to a file. Defaults to session outputs if relative path."""
    p = Path(path)

    # Track allowed boundaries
    allowed_bases = [Path.cwd().resolve()]

    if not p.is_absolute():
        sess_path = active_session_path.get()
        if sess_path:
            outputs_dir = sess_path / "outputs"
            p = outputs_dir / p
            allowed_bases.append(outputs_dir.resolve())

    # Resolve target path and enforce boundaries
    safe_path = p.resolve()

    # Check if target path is within any of the allowed boundaries
    if not any(safe_path.is_relative_to(base) for base in allowed_bases):
        return f"Error writing {path}: Access denied. Path is outside allowed boundaries."

    os.makedirs(safe_path.parent, exist_ok=True)
    try:
        with open(safe_path, "w") as f:
            f.write(content)
        return f"Successfully wrote {safe_path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
