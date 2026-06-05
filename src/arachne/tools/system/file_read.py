"""Read files."""

from pathlib import Path

from arachne.sessions.manager import active_session_path


def read_file(path: str) -> str:
    """Read the contents of a file. Returns first 2000 chars."""
    p = Path(path)

    # Track allowed boundaries
    allowed_bases = [Path.cwd().resolve()]

    if not p.is_absolute() and not p.exists():
        sess_path = active_session_path.get()
        if sess_path:
            outputs_dir = sess_path / "outputs"
            p = outputs_dir / p
            allowed_bases.append(outputs_dir.resolve())

    # Resolve target path and enforce boundaries
    safe_path = p.resolve()

    # Check if target path is within any of the allowed boundaries
    if not any(safe_path.is_relative_to(base) for base in allowed_bases):
        return f"Error reading {path}: Access denied. Path is outside allowed boundaries."

    try:
        with open(safe_path, errors="replace") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"
