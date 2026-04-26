"""Session introspection tools."""

from arachne.sessions.manager import active_session_path


def list_session_files() -> str:
    """List all files in the current session folder (relative paths)."""
    sess_path = active_session_path.get()
    if not sess_path:
        return "No active session."
    files = []
    for p in sorted(sess_path.rglob("*")):
        if p.is_file():
            rel = p.relative_to(sess_path)
            files.append(str(rel))
    if not files:
        return "Session folder is empty."
    return "\n".join(files)
