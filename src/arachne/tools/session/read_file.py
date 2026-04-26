"""Session introspection tools."""

from arachne.sessions.manager import active_session_path


def read_session_file(relative_path: str) -> str:
    """Read a file from the current session folder by relative path."""
    sess_path = active_session_path.get()
    if not sess_path:
        return "No active session."
    p = sess_path / relative_path
    if not p.exists():
        return f"File not found: {relative_path}"
    try:
        content = p.read_text()
        if len(content) > 50000:
            content = content[:25000] + "\n... [TRUNCATED - file too large] ...\n" + content[-25000:]
        return content
    except Exception as e:
        return f"Error reading {relative_path}: {e}"
